"""
sweeps.py -- The single v1 sensitivity study: lambda vs feedstock scarcity.

Sweeps Q_tot from 0 to 18,000 ton/yr in 200 steps, solving the variational
equilibrium at every point, and returns a tidy pandas DataFrame.

It also computes the EXACT locations of the kinks in the sweep analytically
(`kink_points`), which serve three purposes: annotating Figure 2, drawing the
jump discontinuity in Figure 1 correctly rather than as a steep diagonal, and
giving the run summary the abundance threshold to quote.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import data as D
from equilibrium import Equilibrium, aggregate_demand, solve_analytic

__all__ = ["sweep_q_tot", "kink_points", "Kink", "SWEEP_LO", "SWEEP_HI",
           "SWEEP_STEPS", "KINK_REFINE_EPS"]

SWEEP_LO: float = 0.0        # ton/yr   -- SOURCE: brief section 4
SWEEP_HI: float = 18_000.0   # ton/yr   -- SOURCE: brief section 4
SWEEP_STEPS: int = 200       # SOURCE: brief section 4
KINK_REFINE_EPS: float = 0.5   # ton/yr; see sweep_q_tot


@dataclass(frozen=True)
class Kink:
    """A Q_tot value at which the equilibrium's active set changes.

    Attributes:
        q_tot:  Feedstock availability at the kink, ton/yr.
        lam:    Shadow price just at/after the kink, USD/ton.
        agent:  The agent whose status changes.
        cause:  "enters", "hits capacity", or "abundance threshold".
        label:  Ready-to-use annotation text.
    """

    q_tot: float
    lam: float
    agent: str
    cause: str
    label: str


def kink_points(agents: dict[str, D.AgentData] | None = None) -> list[Kink]:
    """Exact Q_tot values where the merit order changes.

    Aggregate demand is piecewise linear in lambda with breakpoints where some
    agent's demand hits zero (lambda = m_i) or its capacity
    (lambda = m_i - b_i*Cap_i).  Mapping each breakpoint through aggregate
    demand gives the Q_tot at which that agent enters or saturates -- exactly,
    with no reliance on the sweep grid.

    Args:
        agents: Agent set; defaults to data.AGENTS.

    Returns:
        Kinks sorted by q_tot.
    """
    ags = D.AGENTS if agents is None else agents
    out: list[Kink] = []

    def clean(q: float) -> float:
        """Round a kink location to 1e-6 ton/yr.

        aggregate_demand evaluated exactly at a breakpoint carries float noise
        of order 1e-12 ton/yr -- e.g. the capacity kink comes back as
        5999.999999999999 rather than 6000.  That is physically meaningless, but
        lambda genuinely JUMPS at these points, so sampling 1.8e-12 to the left
        of one puts the analytic solver on the high branch while the MCP's own
        bound-snapping puts it on the low branch, and the two engines appear to
        disagree by the full height of the jump.  Rounding to a microgram per
        year removes the noise without moving any kink measurably.
        """
        return round(q, 6)

    for k, a in ags.items():
        if a.margin > 0.0:
            q_enter = clean(aggregate_demand(a.margin, ags))
            out.append(Kink(
                q_enter, a.margin, k, "enters",
                f"{k} enters at Q_tot = {q_enter:,.0f} t/yr "
                f"(its margin m_{k} = {a.margin:,.2f} USD/t is reached)",
            ))
        lam_cap = a.margin - a.b * a.cap
        if lam_cap > 0.0:
            q_cap = clean(aggregate_demand(lam_cap, ags))
            out.append(Kink(
                q_cap, lam_cap, k, "hits capacity",
                f"{k} saturates at Q_tot = {q_cap:,.0f} t/yr "
                f"(Cap_{k} = {a.cap:,.0f} t/yr binds)",
            ))
    q_abundant = clean(aggregate_demand(0.0, ags))
    out.append(Kink(
        q_abundant, 0.0, "-", "abundance threshold",
        f"lambda reaches exactly zero at Q_tot = {q_abundant:,.0f} t/yr "
        f"= aggregate unconstrained demand",
    ))
    return sorted(out, key=lambda z: (z.q_tot, z.lam))


def _row(eq: Equilibrium, agents: dict[str, D.AgentData]) -> dict[str, object]:
    """Flatten one Equilibrium into a tidy record.

    Args:
        eq:     Solved equilibrium.
        agents: Agent set.

    Returns:
        Mapping of column name to value, units documented in `sweep_q_tot`.
    """
    row: dict[str, object] = {
        "q_tot_t_per_yr": eq.q_tot,
        "lambda_usd_per_t": eq.lam,
        "total_q_t_per_yr": eq.total_q,
        "unbought_t_per_yr": eq.unbought_feedstock(),
        "shared_constraint_binds": float(eq.lam > 0.0),
        "system_emissions_tco2e_per_yr": eq.system_emissions(),
        "max_kkt_residual": eq.max_residual(),
        "price_setter": ",".join(eq.price_setters(agents)),
    }
    for k in agents:
        row[f"q_{k}_t_per_yr"] = eq.q[k]
        row[f"share_{k}"] = eq.q[k] / eq.q_tot if eq.q_tot > 0 else 0.0
        row[f"mu_{k}_usd_per_t"] = eq.mu[k]
        row[f"state_{k}"] = eq.agent_state(k, agents)
        row[f"op_profit_{k}_usd_per_yr"] = eq.operating_profit(k)
        row[f"net_profit_{k}_usd_per_yr"] = eq.net_profit(k)
        row[f"emissions_{k}_tco2e_per_yr"] = eq.emissions(k)
    row["total_op_profit_usd_per_yr"] = sum(
        eq.operating_profit(k) for k in agents)
    row["total_net_profit_usd_per_yr"] = sum(eq.net_profit(k) for k in agents)
    return row


def sweep_q_tot(
    lo: float = SWEEP_LO,
    hi: float = SWEEP_HI,
    steps: int = SWEEP_STEPS,
    agents: dict[str, D.AgentData] | None = None,
    refine_kinks: bool = True,
    solver=solve_analytic,
) -> pd.DataFrame:
    """Solve the VE across a grid of feedstock availabilities.

    Args:
        lo:           Lowest Q_tot, ton/yr.
        hi:           Highest Q_tot, ton/yr.
        steps:        Number of grid points (the brief specifies 200).
        agents:       Agent set; defaults to data.AGENTS.
        refine_kinks: Add points immediately either side of every exact kink.
                      Without this, lambda's jump discontinuity at Q_tot = Cap_S
                      would be drawn as a steep diagonal between two grid points
                      rather than as the vertical drop it is.
        solver:       Callable (q_tot, agents) -> Equilibrium.  Defaults to the
                      exact analytic solver; pass gnep_mcp.solve_mcp to run the
                      whole sweep through the primary MCP engine instead.

    Returns:
        Tidy DataFrame, one row per Q_tot, sorted by Q_tot.  Columns carry their
        units in the name: q_tot_t_per_yr, lambda_usd_per_t, q_<agent>_t_per_yr,
        share_<agent>, mu_<agent>_usd_per_t, op_profit_<agent>_usd_per_yr,
        net_profit_<agent>_usd_per_yr, emissions_<agent>_tco2e_per_yr,
        state_<agent> (the equilibrium state: AT CAPACITY / PRICE-SETTER /
        PRICED OUT), price_setter, plus system totals and the worst KKT
        residual at that point.
    """
    ags = D.AGENTS if agents is None else agents
    grid = list(np.linspace(lo, hi, steps))
    if refine_kinks:
        # Half a tonne per year either side of each kink.  It has to be large
        # enough that every solver resolves the two sides as genuinely distinct
        # problems: the Fischer-Burmeister residual is scaled by the largest
        # capacity, so an allocation of ~1e-3 t/yr against a 6,000 t/yr scale is
        # below what a Newton method can resolve, and the MCP's own
        # variational-equilibrium gate rejects it (correctly).  0.5 t/yr is
        # 2.8e-5 of the 18,000 t/yr axis, i.e. well under one pixel, so the jump
        # still plots as a clean vertical.
        eps = KINK_REFINE_EPS
        for kink in kink_points(ags):
            for q in (kink.q_tot - eps, kink.q_tot, kink.q_tot + eps):
                if lo <= q <= hi:
                    grid.append(q)
    grid = sorted(set(grid))

    records = [_row(solver(q, ags), ags) for q in grid]
    df = pd.DataFrame.from_records(records)
    return df.sort_values("q_tot_t_per_yr").reset_index(drop=True)
