"""
solver.py -- exact variational equilibrium of the linear-cost feedstock game.

With a constant margin m_i per ton, firm i's best response to a price lambda is
a step: take Cap_i if m_i > lambda, nothing if m_i < lambda, anything if equal.
Aggregate demand D(lambda) = sum of Cap_i over m_i > lambda is a step function,
and the equilibrium price is the lowest lambda >= 0 with D(lambda) <= Q_tot
(the "lower-end" convention; lambda is set-valued exactly at the thresholds).

Firms above lambda run at capacity, firms below take nothing, and a firm exactly
at lambda absorbs the remainder.  The KKT system being solved is

    0 <= q_i      _|_  lambda + mu_i - m_i >= 0
    0 <= mu_i     _|_  Cap_i - q_i         >= 0
    0 <= lambda   _|_  Q_tot - sum q_j     >= 0
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import data as D

EPS = 1e-6


@dataclass
class Equilibrium:
    """Solved equilibrium at one pool size."""

    q_tot: float
    lam: float
    q: dict[str, float]
    mu: dict[str, float]
    info: dict = field(default_factory=dict)

    @property
    def unbought(self) -> float:
        """Waste nobody buys (landfilled), t/yr."""
        return max(0.0, self.q_tot - sum(self.q.values()))


def agents(**overrides) -> dict[str, D.Agent]:
    """Copy of the base agents; overrides like S={'revenue': 1500} replace fields."""
    out = dict(D.AGENTS)
    for k, kw in overrides.items():
        out[k] = dataclasses.replace(out[k], **kw)
    return out


def merit_order(ags: dict[str, D.Agent]) -> list[str]:
    """Firm keys from highest to lowest margin."""
    return sorted(ags, key=lambda k: (-ags[k].margin, k))


def breakpoints(ags: dict[str, D.Agent]) -> list[float]:
    """Pool sizes where the price-setter changes: cumulative capacity in merit order."""
    out, tot = [], 0.0
    for k in merit_order(ags):
        if ags[k].margin <= 0:
            continue
        tot += ags[k].cap
        out.append(tot)
    return out


def _demand(lam: float, ags: dict[str, D.Agent]) -> float:
    return sum(a.cap for a in ags.values() if a.margin > lam)


def solve(q_tot: float = D.Q_TOT_BASE, ags: dict[str, D.Agent] | None = None) -> Equilibrium:
    """Solve the equilibrium exactly at pool size q_tot (t/yr)."""
    ags = D.AGENTS if ags is None else ags
    q_tot = max(0.0, float(q_tot))
    cands = sorted({0.0} | {a.margin for a in ags.values() if a.margin > 0})
    lam = next(c for c in cands if _demand(c, ags) <= q_tot)

    q = {k: (a.cap if a.margin > lam else 0.0) for k, a in ags.items()}
    at_price = [k for k, a in ags.items() if a.margin == lam and lam > 0]
    resid = q_tot - sum(q.values())
    for k in at_price:
        take = min(ags[k].cap, max(0.0, resid))
        q[k] = take
        resid -= take
    mu = {k: (ags[k].margin - lam if ags[k].margin > lam else 0.0) for k in ags}
    return Equilibrium(q_tot, lam, q, mu, {
        "tie": len(at_price) > 1,
        "setter": at_price[0] if len(at_price) == 1 else None,
    })


def state(k: str, eq: Equilibrium, ags: dict[str, D.Agent]) -> str:
    """'at capacity', 'price-setter' or 'priced out'."""
    if eq.q[k] >= ags[k].cap - EPS and ags[k].cap > 0:
        return "at capacity"
    if eq.q[k] > EPS:
        return "price-setter"
    return "priced out"


def kkt_residual(eq: Equilibrium, ags: dict[str, D.Agent]) -> float:
    """Largest violation of any KKT condition (0 at an exact equilibrium)."""
    worst = 0.0
    for k, a in ags.items():
        stat = eq.lam + eq.mu[k] - a.margin
        worst = max(worst, -eq.q[k], -stat, abs(eq.q[k] * stat), -eq.mu[k],
                    eq.q[k] - a.cap, abs(eq.mu[k] * (a.cap - eq.q[k])))
    slack = eq.q_tot - sum(eq.q.values())
    return max(worst, -eq.lam, -slack, abs(eq.lam * slack), 0.0)


def profits(eq: Equilibrium, ags: dict[str, D.Agent] | None = None) -> dict[str, dict]:
    """Operating profit m_i*q_i and profit after capital m_i*q_i - ACC_i, per firm.

    ACC_i is a constant, so it never changes q_i; it only shifts profit.  Profit
    after capital is None for a firm whose capital cost was not supplied.
    """
    ags = D.AGENTS if ags is None else ags
    out = {}
    for k, a in ags.items():
        op = a.margin * eq.q[k]
        out[k] = {"operating": op,
                  "capital": a.acc,
                  "after_capital": None if a.acc is None else op - a.acc}
    return out


def breakeven_tons(a: D.Agent) -> float | None:
    """Tons/yr a firm must process to cover its capital charge: ACC_i / m_i."""
    if a.acc is None or a.margin <= 0:
        return None
    return a.acc / a.margin


def sweep(q_max: float = 40_000.0, n: int = 200,
          ags: dict[str, D.Agent] | None = None) -> pd.DataFrame:
    """Re-solve at n+ pool sizes, with each threshold and points just either side."""
    ags = D.AGENTS if ags is None else ags
    grid = set(np.linspace(0.0, q_max, n + 1).tolist())
    for b in breakpoints(ags):
        if b <= q_max:
            grid.update({b - EPS, b, b + EPS})
    grid.add(D.Q_TOT_BASE)
    rows = []
    for Q in sorted(grid):
        eq = solve(Q, ags)
        assert not eq.info["tie"], f"margin tie at Q={Q}"
        row = {"q_tot": Q, "lambda": eq.lam, "unbought": eq.unbought,
               "setter": eq.info["setter"] or "", "kkt": kkt_residual(eq, ags)}
        for k in ags:
            row[f"q_{k}"] = eq.q[k]
            row[f"mu_{k}"] = eq.mu[k]
        rows.append(row)
    return pd.DataFrame(rows)
