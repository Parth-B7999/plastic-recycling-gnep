"""
plots.py -- Figures 1 and 2, publication quality, colorblind-safe.

PALETTE PROVENANCE
------------------
Series hues are slots 1-3 of the validated reference categorical palette
(blue #2a78d6, orange #eb6834, aqua #1baf7a).  That documented palette records
those three slots as clearing every hard gate on the all-pairs list in both
light and dark mode: worst-pair CVD delta-E 9.2 (target >= 8) and worst-pair
normal-vision delta-E 24.0 (floor >= 15).  Aqua sits below 3:1 contrast on a
light surface, so the relief rule applies and is honoured here: every stacked
band carries a visible direct label, and the full numeric table ships alongside
as sweep_results.csv.

Lambda is a single series and therefore needs no legend -- the axis label names
it -- and is drawn in violet (slot 7, #4a3aa7) to stay clearly distinct from the
three agent hues used in Figure 2.

Figures are static PNG for a manuscript, so there is no hover layer; identity is
carried by direct labels plus a legend, never by colour alone.
"""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import data as D  # noqa: E402
from equilibrium import solve_analytic  # noqa: E402
from sweeps import KINK_REFINE_EPS, Kink  # noqa: E402

__all__ = ["fig1_lambda_vs_qtot", "fig2_merit_order", "RESULTS_DIR",
           "SERIES_COLOR", "FIG1_CAPTION", "FIG2_CAPTION"]

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#8a8984"
GRID = "#e4e3df"
LAMBDA_COLOR = "#4a3aa7"

SERIES_COLOR: dict[str, str] = {
    "S": "#2a78d6",   # slot 1, blue
    "W": "#eb6834",   # slot 2, orange
    "G": "#1baf7a",   # slot 3, aqua
}
SERIES_LABEL: dict[str, str] = {
    "S": "STRAP",
    "W": "Incineration",
    "G": "Gasification (ER)",
}

FIG1_CAPTION = (
    "Figure 1. Equilibrium shadow price of shared feedstock, lambda, against "
    "total feedstock availability Q_tot. lambda is the USD/ton that competition "
    "implicitly adds to the cost of feedstock for every agent. The curve is "
    "piecewise linear and non-increasing, with a jump discontinuity where STRAP "
    "saturates its capacity and the marginal buyer switches from STRAP to "
    "incineration. lambda reaches exactly zero once supply exceeds aggregate "
    "unconstrained demand."
)

FIG2_CAPTION = (
    "Figure 2. Equilibrium allocation of feedstock among the three agents as a "
    "function of availability, showing the merit order in which technologies "
    "enter as waste becomes abundant. Agents enter in descending order of net "
    "linear margin m_i; each kink is labelled with the capacity or margin that "
    "causes it. The gap between the stacked total and the 45-degree line is "
    "feedstock no agent buys, which is landfilled."
)


def _style_axes(ax: plt.Axes) -> None:
    """Apply the recessive grid/axis treatment used by both figures."""
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9, length=3, width=0.8)


def _split_at_jumps(df: pd.DataFrame, x: str, y: str,
                    x_tol: float, y_tol: float) -> list[pd.DataFrame]:
    """Split a curve into continuous branches at its jump discontinuities.

    lambda(Q_tot) genuinely jumps where an agent's capacity saturates at the
    same instant the next agent becomes marginal.  Drawing straight through
    that would render the jump as a steep diagonal and imply values of lambda
    that never occur.

    Args:
        df:    Sweep results, sorted by `x`.
        x:     Abscissa column.
        y:     Ordinate column.
        x_tol: Two points closer than this in x are treated as coincident.
        y_tol: A y change larger than this across coincident x is a jump.

    Returns:
        One DataFrame per continuous branch.
    """
    branches: list[pd.DataFrame] = []
    start = 0
    xs, ys = df[x].to_numpy(), df[y].to_numpy()
    for i in range(1, len(df)):
        if xs[i] - xs[i - 1] <= x_tol and abs(ys[i] - ys[i - 1]) > y_tol:
            branches.append(df.iloc[start:i])
            start = i
    branches.append(df.iloc[start:])
    return [b for b in branches if len(b) > 0]


def fig1_lambda_vs_qtot(
    df: pd.DataFrame,
    kinks: list[Kink],
    path: str | None = None,
    base_q_tot: float = D.Q_TOT_BASE,
) -> str:
    """Draw Figure 1: lambda versus feedstock availability.

    Args:
        df:         Sweep results from sweeps.sweep_q_tot.
        kinks:      Exact kink locations from sweeps.kink_points.
        path:       Output PNG path; defaults to results/fig1_lambda_vs_qtot.png.
        base_q_tot: Base-case feedstock availability to mark, ton/yr.

    Returns:
        The caption string, also written beside the PNG as a .txt file.
    """
    path = path or os.path.join(RESULTS_DIR, "fig1_lambda_vs_qtot.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    span = df["q_tot_t_per_yr"].max() - df["q_tot_t_per_yr"].min()
    # x_tol must exceed the spacing sweeps.sweep_q_tot actually inserts around
    # each kink (2*KINK_REFINE_EPS), or every "coincident" pair looks too far
    # apart in x and no jump is ever detected -- the curve then plots as a
    # continuous (if very steep) line with NONE of the jump annotations below.
    x_tol = max(span * 1e-6, 4.0 * KINK_REFINE_EPS)
    branches = _split_at_jumps(df, "q_tot_t_per_yr", "lambda_usd_per_t",
                               x_tol=x_tol, y_tol=1.0)

    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=200, facecolor=SURFACE)
    _style_axes(ax)

    for br in branches:
        ax.plot(br["q_tot_t_per_yr"], br["lambda_usd_per_t"],
                color=LAMBDA_COLOR, linewidth=2.0, solid_capstyle="round",
                zorder=3)

    # Render each jump honestly: a dashed connector, a filled dot on the value
    # that is attained and an open dot on the one that is not.  The label is
    # derived from the exact kinks, so it names the RIGHT agents at each jump.
    y_top = float(df["lambda_usd_per_t"].max()) * 1.10
    ladder = [0.78, 0.46, 0.30]
    for n, (left, right) in enumerate(zip(branches[:-1], branches[1:])):
        x_j = float(right["q_tot_t_per_yr"].iloc[0])
        y_hi = float(left["lambda_usd_per_t"].iloc[-1])
        y_lo = float(right["lambda_usd_per_t"].iloc[0])
        ax.plot([x_j, x_j], [y_lo, y_hi], color=LAMBDA_COLOR, linewidth=1.2,
                linestyle=(0, (3, 3)), alpha=0.55, zorder=2)
        ax.plot([x_j], [y_hi], marker="o", markersize=5.5,
                markerfacecolor=SURFACE, markeredgecolor=LAMBDA_COLOR,
                markeredgewidth=1.6, zorder=4)
        ax.plot([x_j], [y_lo], marker="o", markersize=5.5,
                color=LAMBDA_COLOR, zorder=4)
        near = [k for k in kinks if abs(k.q_tot - x_j) <= max(1.0, x_j * 1e-6)]
        saturates = next((k.agent for k in near if k.cause == "hits capacity"),
                         None)
        enters = next((k.agent for k in near if k.cause == "enters"), None)
        if saturates and enters:
            what = (f"{SERIES_LABEL[saturates]} saturates;\n"
                    f"{SERIES_LABEL[enters]} becomes marginal")
        else:
            what = "active set changes"
        side = 1  # all jump labels to the right, so leaders never cross
        ax.annotate(
            f"$\\lambda$ jumps {y_hi:,.0f} $\\rightarrow$ {y_lo:,.0f} USD/t\n{what}",
            xy=(x_j, 0.5 * (y_hi + y_lo)),
            xytext=(x_j + side * span * 0.030, y_top * ladder[n]),
            fontsize=8.5, color=INK_SECONDARY,
            ha="left" if side > 0 else "right",
            arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=0.9),
        )

    # Base case: solved EXACTLY at base_q_tot rather than snapped to the sweep
    # grid, which would misreport lambda by ~0.5 USD/ton.
    lam_base = solve_analytic(base_q_tot).lam
    ax.axvline(base_q_tot, color=INK_MUTED, linewidth=1.0,
               linestyle=(0, (2, 3)), zorder=1)
    ax.plot([base_q_tot], [lam_base], marker="o", markersize=8,
            color=LAMBDA_COLOR, markeredgecolor=SURFACE, markeredgewidth=2,
            zorder=5)
    ax.annotate(
        f"base case\n$Q_{{tot}}$ = {base_q_tot:,.0f} t/yr\n"
        f"$\\lambda$ = {lam_base:,.2f} USD/t",
        xy=(base_q_tot, lam_base),
        xytext=(base_q_tot - span * 0.035, y_top * 0.28),
        fontsize=9, color=INK_PRIMARY, ha="right",
        arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=0.9),
    )

    # Abundance threshold.
    thr = next(k for k in kinks if k.cause == "abundance threshold")
    ax.axvline(thr.q_tot, color=INK_MUTED, linewidth=1.0,
               linestyle=(0, (2, 3)), zorder=1)
    ax.annotate(
        f"abundance threshold\n$Q_{{tot}}$ = {thr.q_tot:,.0f} t/yr\n"
        f"$\\lambda$ = 0 beyond here",
        xy=(thr.q_tot, 0.0),
        xytext=(thr.q_tot + span * 0.025, y_top * 0.135),
        fontsize=9, color=INK_PRIMARY, ha="left",
        arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=0.9),
    )

    ax.set_xlabel("Total feedstock availability  $Q_{tot}$  [ton/yr]",
                  fontsize=10, color=INK_PRIMARY)
    ax.set_ylabel("Feedstock scarcity price  $\\lambda$  [USD/ton]",
                  fontsize=10, color=INK_PRIMARY)
    ax.set_title("Competition-implied surcharge on feedstock",
                 fontsize=12, color=INK_PRIMARY, pad=12, loc="left")
    ax.set_xlim(df["q_tot_t_per_yr"].min(), df["q_tot_t_per_yr"].max())
    ax.set_ylim(-40, y_top)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)

    with open(os.path.splitext(path)[0] + "_caption.txt", "w") as fh:
        fh.write(FIG1_CAPTION + "\n")
    return FIG1_CAPTION


def fig2_merit_order(
    df: pd.DataFrame,
    kinks: list[Kink],
    path: str | None = None,
    base_q_tot: float = D.Q_TOT_BASE,
) -> str:
    """Draw Figure 2: stacked-area merit order of feedstock uptake.

    Args:
        df:         Sweep results from sweeps.sweep_q_tot.
        kinks:      Exact kink locations from sweeps.kink_points.
        path:       Output PNG path; defaults to results/fig2_merit_order.png.
        base_q_tot: Base-case feedstock availability to mark, ton/yr.

    Returns:
        The caption string, also written beside the PNG as a .txt file.
    """
    path = path or os.path.join(RESULTS_DIR, "fig2_merit_order.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    x = df["q_tot_t_per_yr"].to_numpy()
    series = [df[f"q_{k}_t_per_yr"].to_numpy() for k in D.AGENT_NAMES]

    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=200, facecolor=SURFACE)
    _style_axes(ax)

    # A 2px surface-coloured edge on each band is the stacked-segment spacer.
    ax.stackplot(
        x, *series,
        colors=[SERIES_COLOR[k] for k in D.AGENT_NAMES],
        labels=[f"{SERIES_LABEL[k]}  ($q_{k}$)" for k in D.AGENT_NAMES],
        edgecolor=SURFACE, linewidth=1.2, zorder=2,
    )
    ax.plot(x, x, color=INK_MUTED, linewidth=1.2, linestyle=(0, (4, 3)),
            zorder=3)
    ax.annotate("45$^\\circ$:  $\\sum_i q_i = Q_{tot}$\n(all feedstock taken up)",
                xy=(16400, 16400), xytext=(12250, 17250), fontsize=8.5,
                color=INK_SECONDARY, ha="left", va="top",
                arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=0.9))

    # The wedge between the stacked total and the 45-degree line is a large
    # empty area, so it is labelled in place with no leader.
    ax.text(15000, 13350, "unbought \u2014 landfilled", fontsize=9,
            color=INK_SECONDARY, ha="center", va="center", style="italic")

    # Direct labels inside each band (the relief rule for the aqua slot).
    label_at = 15_000.0
    idx = int((abs(x - label_at)).argmin())
    lower = 0.0
    for k, s_k in zip(D.AGENT_NAMES, series):
        mid = lower + 0.5 * s_k[idx]
        if s_k[idx] > 700:
            ax.text(label_at, mid, SERIES_LABEL[k], fontsize=9.5,
                    color="#ffffff", ha="center", va="center",
                    fontweight="semibold", zorder=5)
        lower += s_k[idx]

    # Kink annotations, laddered down the free upper-left region so no leader
    # crosses another.  Each states WHICH agent's capacity or margin causes it.
    notes = [
        (6000.0, 6000.0, 11_300,
         "STRAP hits $Cap_S$ = 6,000 t/yr\nincineration starts buying"),
        (10000.0, 10000.0, 14_100,
         "Incineration hits $Cap_W$ = 4,000 t/yr\ngasification starts buying"),
        (11373.7, 11373.7, 17_300,
         "Gasification reaches its own optimum\n"
         "$m_G/b_G$ = 1,374 t/yr, below $Cap_G$;  $\\lambda$ = 0"),
    ]
    for xk, yk, ytext, text in notes:
        ax.axvline(xk, color=INK_MUTED, linewidth=1.0, linestyle=(0, (2, 3)),
                   zorder=1)
        ax.annotate(text, xy=(xk, yk), xytext=(350, ytext), fontsize=8.5,
                    color=INK_SECONDARY, ha="left", va="top",
                    arrowprops=dict(arrowstyle="-", color=INK_MUTED,
                                    linewidth=0.9))

    ax.axvline(base_q_tot, color=INK_PRIMARY, linewidth=1.2,
               linestyle=(0, (1, 2)), zorder=4)
    ax.text(base_q_tot - 200, 8600, "base case", rotation=90, fontsize=8.5,
            color=INK_PRIMARY, ha="right", va="bottom")

    ax.set_xlabel("Total feedstock availability  $Q_{tot}$  [ton/yr]",
                  fontsize=10, color=INK_PRIMARY)
    ax.set_ylabel("Equilibrium feedstock processed  $q_i^*$  [ton/yr]",
                  fontsize=10, color=INK_PRIMARY)
    ax.set_title("Merit order of feedstock uptake", fontsize=12,
                 color=INK_PRIMARY, pad=12, loc="left")
    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(0, 18_000)
    # Legend below the axes: it would otherwise occupy the upper-left region
    # the kink annotations need.
    leg = ax.legend(loc="upper center", frameon=False, fontsize=9, ncol=3,
                    labelcolor=INK_SECONDARY, handlelength=1.4,
                    bbox_to_anchor=(0.5, -0.135), columnspacing=2.0)
    for t in leg.get_texts():
        t.set_color(INK_SECONDARY)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)

    with open(os.path.splitext(path)[0] + "_caption.txt", "w") as fh:
        fh.write(FIG2_CAPTION + "\n")
    return FIG2_CAPTION
