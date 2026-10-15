"""
plots.py -- every figure and the sweep CSV for the report.

Run:  python plots.py     (writes results/fig1..fig5 and results/sweep_q_tot.csv)
"""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
import numpy as np  # noqa: E402

import data as D  # noqa: E402
import solver as S  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
LAM = "#4a3aa7"
COLOR = {"gas": "#2a9d8f", "ccs": "#8ab17d", "strap": "#2f7ad9", "inc": "#e76f3c"}
SHORT = {"gas": "Gasification", "ccs": "Gasification + CCS", "strap": "STRAP", "inc": "Incineration"}
MINUS = "−"


def _fmt(v: float, nd: int = 2) -> str:
    return f"{v:,.{nd}f}".replace("-", MINUS)


def _axes(figsize):
    fig, ax = plt.subplots(figsize=figsize, dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=3)
    return fig, ax


def _save(fig, name):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, name)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
def fig1_margins():
    """Each firm's walk-away price, with the base-case price marked."""
    eq = S.solve()
    keys = S.merit_order(D.AGENTS)
    fig, ax = _axes((7.8, 4.2))
    ys = list(range(len(keys)))[::-1]
    ax.barh(ys, [D.AGENTS[k].margin for k in keys], color=[COLOR[k] for k in keys],
            height=0.55, zorder=3)
    ax.set_yticks(ys)
    ax.set_yticklabels([SHORT[k] for k in keys])
    for y, k in zip(ys, keys):
        ax.text(D.AGENTS[k].margin + 18, y, f"{_fmt(D.AGENTS[k].margin)} USD/t",
                va="center", fontsize=9.5, color=INK)
    ax.axvline(eq.lam, color=LAM, lw=1.6, ls=(0, (5, 3)), zorder=5)
    ax.text(eq.lam + 14, 3.62, f"Base-case price {_fmt(eq.lam)} (set by STRAP)",
            color=LAM, fontsize=9, va="center")
    ax.set_xlim(0, 1700)
    ax.set_ylim(-0.6, 3.9)
    ax.set_xlabel("Most the firm can pay for one more ton of feedstock and still "
                  "break even on operations  [USD/ton]", color=INK2, fontsize=8.8)
    ax.tick_params(axis="y", length=0, labelsize=10)
    ax.grid(axis="y", visible=False)
    ax.set_title("Who can afford the feedstock?  (net margin per ton)", loc="left",
                 color=INK, fontsize=11.5, pad=10)
    return _save(fig, "fig1_margins.png")


def fig2_staircase(df):
    """Price against pool size: five flat steps."""
    fig, ax = _axes((8.2, 4.6))
    x, y = df["q_tot"].to_numpy(), df["lambda"].to_numpy()
    # draw each flat segment separately so jumps are not joined by diagonals
    bps = [0.0] + S.breakpoints(D.AGENTS) + [float(x.max())]
    vals = [D.AGENTS[k].margin for k in S.merit_order(D.AGENTS)] + [0.0]
    for lo, hi, v in zip(bps[:-1], bps[1:], vals):
        ax.plot([lo, hi], [v, v], color=LAM, lw=2.2, zorder=4, solid_capstyle="butt")
    for b in bps[1:-1]:
        ax.axvline(b, color=GRID, lw=1.0, zorder=1)
    # lower-end convention: filled dot on the lower value, open dot on the upper
    for b, hi, lo in zip(bps[1:-1], vals[:-1], vals[1:]):
        ax.plot([b], [hi], "o", ms=6, mfc=SURFACE, mec=LAM, zorder=6)
        ax.plot([b], [lo], "o", ms=6, mfc=LAM, mec=LAM, zorder=6)
    names = {v: k for k, v in zip(S.merit_order(D.AGENTS), vals)}
    order = S.merit_order(D.AGENTS)
    labels = [SHORT[order[0]] + " alone"] + ["+ " + SHORT[k] for k in order[1:]] + ["surplus\nlandfilled"]
    mids = [(lo + hi) / 2 for lo, hi in zip(bps[:-1], bps[1:])]
    mids[-1] = 38_900
    mids[0] = 4_800
    for mid, v, lab in zip(mids, vals, labels):
        ax.text(mid, v + 55, f"{lab}\n{_fmt(v)}", ha="center", va="bottom", fontsize=8.3,
                color=INK2)
    eq = S.solve()
    ax.plot([D.Q_TOT_BASE], [eq.lam], "o", ms=9, mfc="white", mec=INK, mew=2.2, zorder=7)
    ax.annotate("base case\n20,000 t/yr, 932.96", (D.Q_TOT_BASE, eq.lam),
                (D.Q_TOT_BASE + 2500, eq.lam + 330), fontsize=8.8, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK, lw=0.9))
    ax.set_xlim(0, 40_000)
    ax.set_ylim(-60, 1700)
    ax.set_xlabel("Feedstock available  $Q_{tot}$  [ton/yr]", color=INK2, fontsize=9.5)
    ax.set_ylabel("Equilibrium price  $\\lambda$  [USD/ton]", color=INK2, fontsize=9.5)
    ax.set_title("The equilibrium price is a staircase", loc="left", color=INK,
                 fontsize=11.5, pad=10)
    return _save(fig, "fig2_staircase.png")


def fig3_allocation(df):
    """Who gets the waste as the pool grows."""
    fig, ax = _axes((8.2, 4.6))
    x = df["q_tot"].to_numpy()
    order = S.merit_order(D.AGENTS)
    ax.stackplot(x, *[df[f"q_{k}"].to_numpy() for k in order],
                 colors=[COLOR[k] for k in order], labels=[SHORT[k] for k in order],
                 zorder=3, alpha=0.95)
    ax.plot(x, x, color=INK2, lw=1.1, ls=(0, (4, 3)), zorder=5, label="all feedstock bought (45°)")
    ax.legend(loc="upper left", fontsize=8.5, frameon=False)
    ax.text(31_000, 41_000, "above the plants' combined 36,800 t/yr\nthe surplus is landfilled",
            fontsize=8.3, color=INK2, ha="center", va="top")
    ax.set_xlim(0, 40_000)
    ax.set_ylim(0, 42_000)
    ax.set_xlabel("Feedstock available  $Q_{tot}$  [ton/yr]", color=INK2, fontsize=9.5)
    ax.set_ylabel("Tons bought  [ton/yr]", color=INK2, fontsize=9.5)
    ax.set_title("Who gets the waste: firms fill in order of margin", loc="left",
                 color=INK, fontsize=11.5, pad=10)
    return _save(fig, "fig3_allocation.png")


def tornado_rows():
    """Change in the price at the base pool for each assumed input."""
    base = S.solve().lam
    rows = []

    def lam(**kw):
        return S.solve(D.Q_TOT_BASE, S.agents(**kw)).lam - base

    A = D.AGENTS
    rows.append(("STRAP revenue\n$\\pm$10% (147 USD/t)", "strap",
                 lam(strap={"revenue": A["strap"].revenue * 0.9}), lam(strap={"revenue": A["strap"].revenue * 1.1})))
    rows.append(("STRAP operating cost\n$\\pm$10% (54 USD/t)", "strap",
                 lam(strap={"opex": A["strap"].opex * 1.1}), lam(strap={"opex": A["strap"].opex * 0.9})))
    old = D.P_RAW
    D.P_RAW = 100.0
    hi = S.solve().lam - base
    D.P_RAW = -50.0
    lo = S.solve().lam - base
    D.P_RAW = old
    rows.append(("Feedstock price $p_{raw}$\n$-$50 to +100 USD/t", "shared", hi, lo))
    rows.append(("Gasification or Gasification+CCS\nrevenue or cost $\\pm$10%", "gas", 0.0, 0.0))
    rows.append(("Incineration revenue or cost\n$\\pm$10%", "inc", 0.0, 0.0))
    rows.append(("Gasification capacity\n(8,000 to 3,999, or to 12,001)", "cap",
                 lam(gas={"cap": 3999.0}), lam(gas={"cap": 12001.0})))
    rows.append(("STRAP capacity\n(8,000 to 3,999)", "strap", lam(strap={"cap": 3999.0}), 0.0))
    return rows


def fig4_tornado():
    """What moves the headline price."""
    rows = sorted(tornado_rows(), key=lambda r: -(abs(r[2]) + abs(r[3])))
    fig, ax = _axes((8.6, 4.9))
    cols = {"strap": COLOR["strap"], "shared": "#8d8c87", "gas": COLOR["gas"], "inc": COLOR["inc"], "cap": LAM}
    n = len(rows)
    for i, (lab, own, lo, hi) in enumerate(rows):
        y = n - 1 - i
        ax.barh(y, hi - lo, left=lo, height=0.56, color=cols[own], zorder=3,
                hatch="//" if own == "cap" else None, edgecolor=INK if own == "cap" else cols[own])
        if hi == lo == 0:
            ax.text(8, y, "no effect", va="center", fontsize=8.8, color=INK2, style="italic")
        else:
            if lo < 0:
                ax.text(lo - 10, y, _fmt(lo, 1), va="center", ha="right", fontsize=8.6, color=INK)
            if hi > 0:
                ax.text(hi + 10, y, "+" + _fmt(hi, 1), va="center", ha="left", fontsize=8.6, color=INK)
    ax.set_yticks(range(n))
    ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=8.6, color=INK2)
    ax.axvline(0, color=INK, lw=1.2, zorder=4)
    ax.set_xlim(-1000, 420)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Change in price at 20,000 t/yr vs the base case "
                  f"({_fmt(S.solve().lam)} USD/ton)  [USD/ton]", color=INK2, fontsize=9)
    ax.set_title("What moves the headline price?", loc="left", color=INK, fontsize=11.5, pad=10)
    handles = [mpatches.Patch(color=cols["strap"], label="STRAP's own numbers"),
               mpatches.Patch(color=cols["shared"], label="shared input"),
               mpatches.Patch(facecolor=cols["cap"], hatch="//", edgecolor=INK,
                              label="capacity (switches the regime)")]
    ax.legend(handles=handles, loc="lower left", fontsize=8, frameon=False)
    return _save(fig, "fig4_tornado.png")


def fig5_regime_map(n: int = 161):
    """Which firm sets the price, as the gasification and STRAP capacities vary."""
    xs = np.linspace(0, 16_000, n)
    ys = np.linspace(0, 16_000, n)
    code = {"gas": 0, "ccs": 1, "strap": 2, "inc": 3, "none": 4}
    grid = np.zeros((n, n))
    for i, cs in enumerate(ys):
        for j, ch in enumerate(xs):
            ags = S.agents(gas={"cap": float(ch)}, strap={"cap": float(cs)})
            eq = S.solve(D.Q_TOT_BASE, ags)
            if eq.lam == 0:
                grid[i, j] = code["none"]
            else:
                setter = min(ags, key=lambda k: abs(ags[k].margin - eq.lam))
                grid[i, j] = code[setter]
    from matplotlib.colors import ListedColormap
    cm = ListedColormap([COLOR["gas"], COLOR["ccs"], COLOR["strap"], COLOR["inc"], "#e9e8e4"])
    fig, ax = plt.subplots(figsize=(7.6, 5.4), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.imshow(grid, origin="lower", extent=[0, 16_000, 0, 16_000], cmap=cm, vmin=0, vmax=4,
              aspect="auto", alpha=0.85, interpolation="nearest")
    ax.plot([8000], [8000], "o", ms=10, mfc="white", mec=INK, mew=2.4)
    ax.annotate("", (4000, 8000), (8000, 8000), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.2))
    ax.annotate("", (12000, 8000), (8000, 8000), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.2))
    ax.text(6000, 8500, "$-$4,000", ha="center", fontsize=8.5, color=INK)
    ax.text(10000, 8500, "+4,000", ha="center", fontsize=8.5, color=INK)
    ax.annotate("base case (8,000; 8,000)", (8000, 8000), (9300, 5000), fontsize=9, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK, lw=0.9))
    ax.set_xlabel("Gasification capacity  [ton/yr]", color=INK2, fontsize=9.5)
    ax.set_ylabel("STRAP capacity  [ton/yr]", color=INK2, fontsize=9.5)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.set_title("Which firm sets the price at 20,000 t/yr?", loc="left", color=INK,
                 fontsize=11.5, pad=10)
    handles = [mpatches.Patch(color=COLOR["gas"], alpha=0.85, label="Gasification sets it (1,410.00)"),
               mpatches.Patch(color=COLOR["strap"], alpha=0.85, label="STRAP sets it (932.96)"),
               mpatches.Patch(color=COLOR["inc"], alpha=0.85, label="Incineration sets it (121.47)")]
    ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.95)
    return _save(fig, "fig5_regime_map.png")



def fig6_profit():
    """Profit after capital: base case by firm, and against the amount of waste."""
    eq = S.solve()
    P = S.profits(eq)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.2, 4.5), dpi=200,
                                 gridspec_kw={"width_ratios": [1, 1.25]})
    fig.patch.set_facecolor(SURFACE)
    keys = [k for k in S.merit_order(D.AGENTS) if D.AGENTS[k].acc is not None]
    xs = np.arange(len(keys))
    w = 0.26
    op = [P[k]["operating"] / 1e6 for k in keys]
    cap = [-D.AGENTS[k].acc / 1e6 for k in keys]
    net = [P[k]["after_capital"] / 1e6 for k in keys]
    a1.set_facecolor(SURFACE)
    a1.bar(xs - w, op, w, color="#9bb9e8", label="operating profit", zorder=3)
    a1.bar(xs, cap, w, color="#c9c8c3", label="annualized capital", zorder=3)
    a1.bar(xs + w, net, w, color=[COLOR[k] for k in keys], label="profit after capital", zorder=3)
    for x, v in zip(xs + w, net):
        a1.text(x, v + (0.25 if v >= 0 else -0.25), _fmt(v, 2), ha="center",
                va="bottom" if v >= 0 else "top", fontsize=8.5, color=INK)
    a1.axhline(0, color=INK, lw=1)
    a1.set_xticks(xs)
    a1.set_xticklabels([SHORT[k] for k in keys], fontsize=9)
    a1.set_ylabel("million USD per year", color=INK2, fontsize=9)
    a1.set_ylim(-9, 14)
    a1.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    a1.set_axisbelow(True)
    for s in ("top", "right"):
        a1.spines[s].set_visible(False)
    a1.legend(loc="upper right", fontsize=8, frameon=False)
    a1.set_title("Base case, 20,000 t/yr", loc="left", color=INK, fontsize=11, pad=8)
    a1.tick_params(colors=INK2, labelsize=9)

    a2.set_facecolor(SURFACE)
    Q = np.linspace(0, 40_000, 401)
    for k in keys:
        y = [S.profits(S.solve(q))[k]["after_capital"] / 1e6 for q in Q]
        a2.plot(Q, y, color=COLOR[k], lw=2, label=SHORT[k])
    a2.axhline(0, color=INK, lw=1)
    a2.axvline(D.Q_TOT_BASE, color=INK2, lw=1, ls=(0, (4, 3)))
    a2.text(D.Q_TOT_BASE + 400, 8.6, "base case", fontsize=8.5, color=INK2)
    q0 = 16000 + S.breakeven_tons(D.AGENTS["strap"])
    a2.plot([q0], [0], "o", ms=7, mfc="white", mec=COLOR["strap"], mew=2, zorder=5)
    a2.annotate(f"STRAP breaks even\nat {q0:,.0f} t/yr", (q0, 0), (27_500, -4.8), fontsize=8.5,
                color=INK, arrowprops=dict(arrowstyle="-", color=INK, lw=0.9))
    a2.set_xlim(0, 40_000)
    a2.set_ylim(-9, 10)
    a2.grid(True, color=GRID, lw=0.8)
    a2.set_axisbelow(True)
    for s in ("top", "right"):
        a2.spines[s].set_visible(False)
    a2.set_xlabel("Feedstock available  $Q_{tot}$  [ton/yr]", color=INK2, fontsize=9)
    a2.set_ylabel("profit after capital  [million USD/yr]", color=INK2, fontsize=9)
    a2.legend(loc="lower right", fontsize=8, frameon=False)
    a2.set_title("Profit after capital against the amount of waste", loc="left",
                 color=INK, fontsize=11, pad=8)
    a2.tick_params(colors=INK2, labelsize=9)
    return _save(fig, "fig6_profit.png")

if __name__ == "__main__":
    df = S.sweep()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    df.to_csv(os.path.join(RESULTS_DIR, "sweep_q_tot.csv"), index=False)
    for p in (fig1_margins(), fig2_staircase(df), fig3_allocation(df), fig4_tornado(),
              fig5_regime_map(), fig6_profit()):
        print(p)
    for r in tornado_rows():
        print(r)
