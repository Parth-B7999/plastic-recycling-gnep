"""
check.py -- independent checks behind the "what we checked" claims in the report.

Each check rebuilds the answer a different way and compares it with solver.py:

  1. MARGINS      re-typed from Paola's table, not read from data.py.
  2. PLANNER LP   a planner maximizing total operating profit is a linear
                  program; its allocation and duals must equal the game's
                  (an exact potential game).
  3. BRUTE FORCE  smallest candidate price whose demand fits the pool.
  4. KKT          every complementarity residual of the sweep is zero.
  5. SHAPE        price never rises with the pool; margins never tie.
  6. IDENTITIES   profit = lambda*Q + sum(mu_i*Cap_i); lambda is the margin of
                  the firm where cumulative capacity (best margin first) crosses Q.
  7. RANDOM       the solver agrees with an LP on random 4-firm instances.

Run:  python check.py     (exit code 0 only if every check passes)
"""

from __future__ import annotations

import sys

import numpy as np
from scipy.optimize import linprog

import data as D
import solver as S

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"   {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def lp(m, cap, Q):
    """Planner LP: max sum m_i q_i  s.t. q_i <= cap_i, sum q_i <= Q."""
    return linprog(-np.asarray(m), A_ub=[np.ones(len(m))], b_ub=[Q],
                   bounds=[(0, c) for c in cap], method="highs")


print("1. Margins re-typed from Paola's table")
raw = {"gas": 1635 - 224.9986765, "ccs": 1635 + 270 - 494.234432,   # 270 = 45Q credit
       "strap": 1468.386 - 535.4271538, "inc": 259.5664195 - 138.0970614}
for k in D.KEYS:
    check(f"m_{k} = {raw[k]:,.4f}", abs(raw[k] - D.AGENTS[k].margin) < 1e-9)
check("ranking is CCS > Gasification > STRAP > Incineration", S.merit_order(D.AGENTS) == ["ccs", "gas", "strap", "inc"])

print("\n2. Planner LP at the base pool")
m = np.array([raw[k] for k in D.KEYS])
cap = np.array([D.AGENTS[k].cap for k in D.KEYS])
eq = S.solve(D.Q_TOT_BASE)
res = lp(m, cap, D.Q_TOT_BASE)
qg = np.array([eq.q[k] for k in D.KEYS])
check("LP allocation equals the game's", np.allclose(res.x, qg, atol=1e-6),
      f"LP {np.round(res.x, 2)}  game {qg}")
check("LP pool dual equals lambda*", abs(-res.ineqlin.marginals[0] - eq.lam) < 1e-6,
      f"{-res.ineqlin.marginals[0]:.4f} vs {eq.lam:.4f}")
for i, k in enumerate(D.KEYS):
    check(f"LP capacity dual of {k} equals mu_{k}",
          abs(-res.upper.marginals[i] - eq.mu[k]) < 1e-6,
          f"{-res.upper.marginals[i]:.4f} vs {eq.mu[k]:.4f}")

print("\n3. Full sweep against brute force and the planner LP")
df = S.sweep()
cands = sorted({0.0} | {x for x in m if x > 0})
bps = S.breakpoints(D.AGENTS)
bad_bf = bad_lp = 0
for _, r in df.iterrows():
    Q = r["q_tot"]
    lam_bf = next(c for c in cands if sum(cap[i] for i in range(4) if m[i] > c) <= Q + 1e-9)
    bad_bf += abs(lam_bf - r["lambda"]) > 1e-6
    if not any(abs(Q - b) < 1e-3 for b in bps):
        x = lp(m, cap, Q).x
        bad_lp += not np.allclose(x, [r[f"q_{k}"] for k in D.KEYS], atol=1e-4)
check(f"brute-force price matches at all {len(df)} points", bad_bf == 0, f"{bad_bf} mismatches")
check("planner-LP allocation matches away from thresholds", bad_lp == 0, f"{bad_lp} mismatches")

print("\n4-5. KKT and shape")
check("worst KKT residual is zero", df["kkt"].max() <= 1e-8, f"worst = {df['kkt'].max():.1e}")
lam = df["lambda"].to_numpy()
check("price never rises with the pool", bool(np.all(np.diff(lam) <= 1e-9)))
vals = sorted(set(np.round(lam, 6)))
check("price takes exactly five values",
      vals == sorted({0.0, *np.round(m, 6)}), f"{[round(v, 2) for v in vals]}")
check("thresholds are 8,000 / 16,000 / 24,000 / 36,800",
      np.allclose(bps, [8000, 16000, 24000, 36800]), f"{bps}")
check("no two firms tie on margin", len({round(x, 9) for x in m}) == 4)

print("\n6. Identities quoted in the report")
op = sum(D.AGENTS[k].margin * eq.q[k] for k in D.KEYS)
rent = sum(eq.mu[k] * D.AGENTS[k].cap for k in D.KEYS)
check("operating profit = lambda*Q + capacity rent",
      abs(op - (eq.lam * D.Q_TOT_BASE + rent)) < 1e-6,
      f"{op:,.0f} = {eq.lam * D.Q_TOT_BASE:,.0f} + {rent:,.0f}")
check("base-case price is STRAP's margin", abs(eq.lam - raw["strap"]) < 1e-9)
check("base-case split is Gasification 8,000 / CCS 8,000 / STRAP 4,000 / Incineration 0",
      [eq.q[k] for k in D.KEYS] == [8000.0, 8000.0, 4000.0, 0.0])


# at the base pool the price is the THIRD-highest margin whenever the two best
# firms cannot cover the pool and the best three can (true of the base capacities)
n3 = ok3 = 0
rng3 = np.random.default_rng(2)
for _ in range(3000):
    mm = rng3.uniform(-100, 1700, 4)
    order = np.argsort(-mm)
    ags = {k: S.dataclasses.replace(D.AGENTS[k], revenue=D.AGENTS[k].opex + mm[i] + D.P_RAW)
           for i, k in enumerate(D.KEYS)}
    caps = np.array([ags[k].cap for k in D.KEYS])
    if not (caps[order[:2]].sum() < D.Q_TOT_BASE <= caps[order[:3]].sum()):
        continue
    n3 += 1
    ok3 += abs(S.solve(D.Q_TOT_BASE, ags).lam - max(0.0, mm[order[2]])) < 1e-6
check(f"lambda(20,000) = third-highest margin  ({n3} random margin sets)", n3 > 0 and ok3 == n3)

print("\n7. Random 4-firm instances (solver vs LP)")
rng = np.random.default_rng(1)
n_ok = n = 0
for _ in range(3000):
    mm = rng.uniform(-100, 1500, 4)
    cc = rng.uniform(2000, 14000, 4)
    Q = rng.uniform(1000, 40000)
    ags = {k: S.dataclasses.replace(D.AGENTS[k], revenue=D.AGENTS[k].opex + mm[i] + D.P_RAW,
                                    cap=float(cc[i])) for i, k in enumerate(D.KEYS)}
    e = S.solve(Q, ags)
    if e.info["tie"]:
        continue
    r = lp(mm, cc, Q)
    n += 1
    n_ok += (np.allclose(r.x, [e.q[k] for k in D.KEYS], atol=1e-4)
             and abs(-r.ineqlin.marginals[0] - e.lam) < 1e-5
             and S.kkt_residual(e, ags) < 1e-8)
check(f"solver matches LP allocation, price and KKT on {n} random instances", n_ok == n,
      f"{n - n_ok} mismatches")

print("\n8. Capital in the objective (annualized capex typed from Paola's table)")
acc = {"gas": 5.99978824e6, "ccs": 7.077509116e6, "strap": 6.314455733e6}
P = S.profits(eq)
for k in acc:
    want = raw[k] * eq.q[k] - acc[k]
    check(f"profit after capital, {k}: {want:,.0f}", abs(P[k]["after_capital"] - want) < 1e-6)
check("incineration capital is reported as missing, not zero", P["inc"]["after_capital"] is None)
for k in acc:
    check(f"break-even tons, {k}: {acc[k] / raw[k]:,.1f}",
          abs(S.breakeven_tons(D.AGENTS[k]) - acc[k] / raw[k]) < 1e-6)
q0 = acc["strap"] / raw["strap"]
lo = S.profits(S.solve(16000 + q0 - 5))["strap"]["after_capital"]
hi = S.profits(S.solve(16000 + q0 + 5))["strap"]["after_capital"]
check(f"STRAP covers its capital exactly from {16000 + q0:,.0f} t/yr", lo < 0 < hi)
# capital is a constant: adding it to the planner's objective must not move the allocation
res_c = linprog(-m, A_ub=[np.ones(4)], b_ub=[D.Q_TOT_BASE], bounds=[(0, c) for c in cap], method="highs")
check("capital does not change the planner's allocation", np.allclose(res_c.x, qg))

print()
if failures:
    print(f"FAILED: {len(failures)} check(s): {failures}")
    sys.exit(1)
print("All checks passed.")
