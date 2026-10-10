"""
linear_model.py -- the LINEAR-cost special case of the GNEP, and its SA-1 sweep.

Every agent's operating cost here is purely linear in throughput,

    OPEX_i(q) = a_i * q          [USD/yr],   a_i = OPEX_i^ref / q_i^ref

so profit is affine in q_i:  pi_i = m_i*q_i - ACC_i,  with the net margin

    m_i = REV_i - a_i - p_raw - c_lf*rho_i        [USD/ton]

a CONSTANT, independent of q_i.  This is the model documented in
Report/report_linear.tex.

WHY THIS MODULE EXISTS SEPARATELY FROM equilibrium.py
-----------------------------------------------------
equilibrium.py, gnep_mcp.py, planner.py and best_response.py all evaluate the
smooth interior best response  q_i(lambda) = clip((m_i - lambda)/b_i, 0, Cap_i),
which DIVIDES BY b_i.  At b_i = 0 that expression does not exist -- and not
merely numerically: with linear cost there IS no interior optimum.  An agent
wants everything it can get if m_i > lambda, nothing if m_i < lambda, and is
exactly indifferent across its whole feasible range if m_i = lambda.  The
equilibrium therefore has to be found by a merit-order walk, not by inverting a
demand curve, so it gets its own solver here rather than a special case bolted
into equilibrium.py.

THE SOLUTION, IN ONE PARAGRAPH
------------------------------
Aggregate demand at price lambda is the STEP function
D(lambda) = sum of Cap_i over every agent with m_i > lambda.  The equilibrium
price is the project-wide lower-end convention

    lambda* = min { lambda >= 0 : D(lambda) <= Q_tot }

which is always attained at one of the finitely many candidate prices
{0} union {m_i : m_i > 0}, since D only steps there.  Agents strictly above
lambda* run flat out; agents strictly below take nothing; an agent sitting
exactly AT lambda* is indifferent and is handed precisely the residual needed
to clear the shared pool.

DEGENERACY, REPORTED NOT HIDDEN
-------------------------------
If two agents share the same margin and both sit at lambda*, the split of the
residual between them is genuinely non-unique -- each is indifferent, so
nothing in the model picks one split over another.  `solve_linear` flags this
in `Equilibrium.info["tie_degenerate"]` rather than silently returning one
arbitrary point of that set.  It does not occur at the base-case parameters
(m_S, m_W, m_G are distinct), and `sweep_q_tot` asserts it never occurs across
the whole sweep.
"""

from __future__ import annotations

import dataclasses
import os

import numpy as np
import pandas as pd

import data as D
from equilibrium import (
    STATE_AT_CAPACITY,
    STATE_PRICE_SETTER,
    STATE_PRICED_OUT,
    Equilibrium,
)

__all__ = [
    "linear_agents", "solve_linear", "kkt_residuals", "agent_state",
    "sweep_q_tot", "merit_order", "breakpoints", "RESULTS_DIR",
]

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# Two throughputs closer than this are the same point for sweep purposes.
JUMP_EPS = 1e-6


# =============================================================================
# 1.  Agents under linear cost
# =============================================================================

def linear_agents() -> dict[str, D.AgentData]:
    """Return the three agents with purely linear OPEX (b_i = 0, a_i = average).

    a_i is the plain reference average operating cost -- for incineration and
    gasification that figure is already quoted per ton, so it is used as-is;
    for STRAP it is the reference-year total divided by the reference
    throughput.  No curvature assumption enters anywhere.

    Cross-checked against data.calibrate_opex's own documented b -> 0 limit
    (ratio = 1.0), which must return exactly these coefficients.

    Returns:
        dict[str, AgentData] covering data.AGENT_NAMES, every b = 0.0.
    """
    a = {
        "S": D.OPEX_S_REF / D.Q_REF_S,
        "W": D.OPEX_W_PER_TON,
        "G": D.OPEX_G_PER_TON,
    }
    # The existing, test-covered calibration routine must agree at its own
    # linear endpoint; if it ever stops agreeing, these are not the same model.
    for key, (opex_ref, q_ref, cap) in {
        "S": (D.OPEX_S_REF, D.Q_REF_S, D.CAP_S),
        "W": (D.OPEX_W_PER_TON * D.CAP_W, D.CAP_W, D.CAP_W),
        "G": (D.OPEX_G_PER_TON * D.CAP_G, D.CAP_G, D.CAP_G),
    }.items():
        a_ref, b_ref = D.calibrate_opex(opex_ref, q_ref, cap, ratio=1.0)
        assert b_ref == 0.0, f"{key}: calibrate_opex(ratio=1) gave b={b_ref}"
        assert abs(a_ref - a[key]) <= 1e-9 * max(1.0, abs(a[key])), (
            f"{key}: direct average cost {a[key]} != calibrate_opex {a_ref}"
        )

    return {k: dataclasses.replace(D.AGENTS[k], a=a[k], b=0.0)
            for k in D.AGENT_NAMES}


def merit_order(agents: dict[str, D.AgentData]) -> list[str]:
    """Agent keys sorted by net margin, richest first (ties broken by key)."""
    return sorted(agents, key=lambda k: (-agents[k].margin, k))


def breakpoints(agents: dict[str, D.AgentData]) -> list[float]:
    """Feedstock levels at which the marginal agent changes, ascending.

    Under linear cost lambda(Q_tot) is piecewise CONSTANT, stepping down each
    time the current marginal agent saturates.  Those steps sit exactly at the
    cumulative capacities of the participating (m_i > 0) agents, taken in merit
    order.

    Args:
        agents: Agent set.

    Returns:
        Cumulative capacity levels, ascending; [] if nobody participates.
    """
    out: list[float] = []
    total = 0.0
    for k in merit_order(agents):
        if agents[k].margin <= 0.0:
            continue
        total += agents[k].cap
        out.append(total)
    return out


# =============================================================================
# 2.  Equilibrium
# =============================================================================

def _aggregate_demand(lam: float, agents: dict[str, D.AgentData]) -> float:
    """Feedstock strictly demanded at price `lam`: sum of Cap over m_i > lam."""
    return sum(a.cap for a in agents.values() if a.margin > lam)


def solve_linear(
    q_tot: float = D.Q_TOT_BASE,
    agents: dict[str, D.AgentData] | None = None,
) -> Equilibrium:
    """Solve the variational equilibrium of the LINEAR-cost game exactly.

    lambda* = min{lambda >= 0 : aggregate_demand(lambda) <= Q_tot}, evaluated
    over the finitely many candidate prices where the step function changes.
    Agents above lambda* run at capacity, agents below take nothing, and an
    agent exactly at lambda* absorbs the residual that clears the shared pool.

    Args:
        q_tot:  Feedstock availability, ton/yr.
        agents: Agent set; defaults to `linear_agents()`.

    Returns:
        Equilibrium with method="linear-merit-order".  `info` carries
        `tie_degenerate` (True if two or more indifferent agents shared the
        residual, making the individual split non-unique), `marginal_agent`,
        and `unbought_feedstock`.
    """
    ags = linear_agents() if agents is None else agents
    q_tot = max(0.0, float(q_tot))

    candidates = sorted({0.0} | {a.margin for a in ags.values() if a.margin > 0.0})
    lam = next(c for c in candidates if _aggregate_demand(c, ags) <= q_tot)

    q = {k: (a.cap if a.margin > lam else 0.0) for k, a in ags.items()}
    indifferent = [k for k, a in ags.items() if a.margin == lam and lam > 0.0]

    residual = q_tot - sum(q.values())
    for k in indifferent:                      # clear the pool, capacity-limited
        take = min(ags[k].cap, max(0.0, residual))
        q[k] = take
        residual -= take

    mu = {k: (ags[k].margin - lam if q[k] >= ags[k].cap - JUMP_EPS
              and ags[k].margin > lam else 0.0) for k in ags}

    return Equilibrium(
        q=q, mu=mu, multipliers={"lambda": lam}, q_tot=q_tot,
        method="linear-merit-order",
        info={
            "tie_degenerate": len(indifferent) > 1,
            "marginal_agent": indifferent[0] if len(indifferent) == 1 else None,
            "unbought_feedstock": max(0.0, q_tot - sum(q.values())),
        },
    )


def agent_state(key: str, eq: Equilibrium, agents: dict[str, D.AgentData]) -> str:
    """Equilibrium state of `key`: where it actually sits at the solved price."""
    q, cap = eq.q[key], agents[key].cap
    if q >= cap - JUMP_EPS and cap > 0.0:
        return STATE_AT_CAPACITY
    if q > JUMP_EPS:
        return STATE_PRICE_SETTER
    return STATE_PRICED_OUT


def kkt_residuals(
    eq: Equilibrium, agents: dict[str, D.AgentData]
) -> dict[str, float]:
    """Every complementarity residual of the linear-cost KKT system.

    With b_i = 0 the stationarity term is  lambda + mu_i - m_i,  which unlike
    the quadratic case does NOT depend on q_i.  All entries must be 0 (to
    floating point) at a valid variational equilibrium.

    Args:
        eq:     Solved equilibrium.
        agents: The agent set `eq` was solved against.

    Returns:
        Mapping from residual name to absolute violation.
    """
    res: dict[str, float] = {}
    lam = eq.lam
    for k, ag in agents.items():
        q, mu = eq.q[k], eq.mu[k]
        stat = lam + mu - ag.margin
        res[f"q_{k}>=0"] = max(0.0, -q)
        res[f"stat_{k}>=0"] = max(0.0, -stat)
        res[f"compl_q_{k}"] = abs(q * stat)
        res[f"mu_{k}>=0"] = max(0.0, -mu)
        res[f"cap_slack_{k}>=0"] = max(0.0, q - ag.cap)
        res[f"compl_mu_{k}"] = abs(mu * (ag.cap - q))
    slack = eq.q_tot - sum(eq.q.values())
    res["lambda>=0"] = max(0.0, -lam)
    res["shared_slack>=0"] = max(0.0, -slack)
    res["compl_lambda"] = abs(lam * slack)
    return res


# =============================================================================
# 3.  SA-1 -- lambda versus feedstock scarcity
# =============================================================================

def sweep_q_tot(
    q_max: float = 18_000.0,
    n: int = 200,
    agents: dict[str, D.AgentData] | None = None,
) -> pd.DataFrame:
    """Sweep feedstock availability and re-solve the equilibrium at every point.

    The staircase's jumps are resolved exactly by inserting each breakpoint
    together with points a hair either side of it, so the flat segments and the
    discontinuities are both represented faithfully rather than being joined by
    a spurious diagonal.

    Args:
        q_max:  Upper end of the sweep, ton/yr.
        n:      Number of evenly spaced points before breakpoint refinement.
        agents: Agent set; defaults to `linear_agents()`.

    Returns:
        Tidy DataFrame, one row per Q_tot, carrying lambda, every q_i, mu_i and
        state, the landfilled remainder, and the worst KKT residual at that
        point.

    Raises:
        RuntimeError: if any swept point violates a KKT condition, or if a
            degenerate margin tie is ever encountered.
    """
    ags = linear_agents() if agents is None else agents

    grid = set(np.linspace(0.0, q_max, n).tolist())
    for bp in breakpoints(ags):
        if bp <= q_max:
            grid.update({bp - JUMP_EPS, bp, bp + JUMP_EPS})
    grid.add(D.Q_TOT_BASE)

    rows = []
    worst = 0.0
    for q_tot in sorted(x for x in grid if x >= 0.0):
        eq = solve_linear(q_tot, ags)
        if eq.info["tie_degenerate"]:
            raise RuntimeError(
                f"degenerate margin tie at Q_tot={q_tot:,.6g}: the individual "
                f"allocation is not unique, so this sweep cannot report one"
            )
        resid = max(kkt_residuals(eq, ags).values())
        worst = max(worst, resid)
        if resid > 1e-8:
            raise RuntimeError(
                f"KKT violation {resid:.3e} at Q_tot={q_tot:,.6g}"
            )
        row = {
            "q_tot_t_per_yr": q_tot,
            "lambda_usd_per_t": eq.lam,
            "unbought_t_per_yr": eq.info["unbought_feedstock"],
            "marginal_agent": eq.info["marginal_agent"] or "",
            "max_kkt_residual": resid,
        }
        for k in D.AGENT_NAMES:
            row[f"q_{k}_t_per_yr"] = eq.q[k]
            row[f"mu_{k}_usd_per_t"] = eq.mu[k]
            row[f"state_{k}"] = agent_state(k, eq, ags)
        rows.append(row)

    df = pd.DataFrame(rows).sort_values("q_tot_t_per_yr").reset_index(drop=True)
    df.attrs["worst_kkt_residual"] = worst
    return df
