"""
plots_linear.py -- SA-1 figures for the LINEAR-cost model (report_linear.tex).

Palette, surface and axis treatment are imported from plots.py rather than
duplicated, so the linear-cost figures sit beside the existing ones without
drifting.  See that module's header for the palette's provenance and the
colour-blind gates it clears.

WHY THESE FIGURES LOOK DIFFERENT FROM plots.fig1/fig2
-----------------------------------------------------
Under linear cost lambda(Q_tot) is piecewise CONSTANT, not piecewise linear:
a marginal agent under constant marginal cost sets one price and holds it for
as long as it is the marginal agent, so the curve is a staircase of flat
treads separated by vertical drops.  Drawing it with the usual line plot would
imply intermediate prices that the model never produces, so each tread is
drawn as its own flat segment, closed at the end it attains and open at the
end it does not.
"""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import data as D  # noqa: E402
import linear_model as L  # noqa: E402
from plots import (  # noqa: E402
    GRID,
    INK_MUTED,
    INK_PRIMARY,
    INK_SECONDARY,
    LAMBDA_COLOR,
    RESULTS_DIR,
    SERIES_COLOR,
    SERIES_LABEL,
    SURFACE,
    _style_axes,
)

__all__ = ["figL1_lambda_staircase", "figL2_allocation", "FIGL1_CAPTION",
           "FIGL2_CAPTION"]

FIGL1_CAPTION = (
    "Figure 1. Equilibrium shadow price of shared feedstock, lambda, against "
    "total feedstock availability Q_tot, under linear operating cost. lambda "
    "is piecewise CONSTANT: whichever agent is on the margin has a constant "
    "marginal cost, so it holds one price for as long as it is marginal. The "
    "price steps down each time the marginal agent saturates -- at Q_tot = "
    "Cap_S = 6,000 t/yr, where the marginal buyer switches from STRAP to "
    "incineration, and at Q_tot = Cap_S + Cap_W = 10,000 t/yr, where feedstock "
    "becomes abundant and lambda falls to zero. Gasification never enters at "
    "any Q_tot because its net margin is negative."
)

FIGL2_CAPTION = (
    "Figure 2. Equilibrium allocation of feedstock among the three agents "
    "against availability, under linear operating cost. Agents fill in strict "
    "merit order of net margin m_i: STRAP absorbs everything up to its own "
    "6,000 t/yr capacity, incineration then absorbs the next 4,000 t/yr, and "
    "gasification never enters because m_G < 0. Beyond 10,000 t/yr the gap "
    "between the stacked total and the 45-degree line is feedstock no agent "
    "buys, which is landfilled."
)


def _write_caption(path: str, caption: str) -> str:
    """Write `caption` beside the PNG at `path` and return it."""
    with open(os.path.splitext(path)[0] + "_caption.txt", "w") as fh:
        fh.write(caption + "\n")
    return caption


def _treads(df: pd.DataFrame) -> list[pd.DataFrame]:
    """Split the staircase into its flat treads, one per distinct lambda run."""
    runs, start = [], 0
    lam = df["lambda_usd_per_t"].to_numpy()
    for i in range(1, len(df)):
        if abs(lam[i] - lam[i - 1]) > 1e-9:
            runs.append(df.iloc[start:i])
            start = i
    runs.append(df.iloc[start:])
    return [r for r in runs if len(r) > 0]


def figL1_lambda_staircase(
    df: pd.DataFrame,
    path: str | None = None,
    base_q_tot: float = D.Q_TOT_BASE,
) -> str:
    """Draw the lambda-versus-availability staircase.

    Args:
        df:         Sweep results from linear_model.sweep_q_tot.
        path:       Output PNG path; defaults to results/figL1_lambda_staircase.png.
        base_q_tot: Base-case feedstock availability to mark, ton/yr.

    Returns:
        The caption string, also written beside the PNG as a .txt file.
    """
    path = path or os.path.join(RESULTS_DIR, "figL1_lambda_staircase.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=200, facecolor=SURFACE)
    _style_axes(ax)

    treads = _treads(df)
    for n, tread in enumerate(treads):
        x0 = float(tread["q_tot_t_per_yr"].iloc[0])
        x1 = float(tread["q_tot_t_per_yr"].iloc[-1])
        y = float(tread["lambda_usd_per_t"].iloc[0])
        ax.plot([x0, x1], [y, y], color=LAMBDA_COLOR, linewidth=2.0,
                solid_capstyle="round", zorder=3)
        # Each tread attains its LEFT end and not its right: at a breakpoint
        # lambda has already dropped to the next tread's value.  The final
        # tread has no breakpoint to its right -- it simply runs off the plot
        # -- so it gets no open marker, which would wrongly imply lambda = 0
        # is never attained out there.
        ax.plot([x0], [y], marker="o", markersize=5, color=LAMBDA_COLOR,
                markeredgecolor=SURFACE, markeredgewidth=1.4, zorder=4)
        if n < len(treads) - 1:
            ax.plot([x1], [y], marker="o", markersize=5, markerfacecolor=SURFACE,
                    markeredgecolor=LAMBDA_COLOR, markeredgewidth=1.4, zorder=4)

    # Vertical guides at the two jumps, annotated with what causes each.
    for x_j, label in ((D.CAP_S, r"$Q_{tot}=\mathrm{Cap}_S$"),
                       (D.CAP_S + D.CAP_W, r"$Q_{tot}=\mathrm{Cap}_S+\mathrm{Cap}_W$")):
        ax.axvline(x_j, color=GRID, linewidth=1.0, linestyle=(0, (4, 3)), zorder=1)
        ax.text(x_j, ax.get_ylim()[1], f" {label}", color=INK_MUTED, fontsize=8,
                ha="left", va="top", rotation=90)

    ax.plot([base_q_tot], [df.loc[df.q_tot_t_per_yr == base_q_tot,
                                  "lambda_usd_per_t"].iloc[0]],
            marker="D", markersize=6, color=LAMBDA_COLOR,
            markeredgecolor=SURFACE, markeredgewidth=1.6, zorder=5)
    ax.annotate(
        f"base case\n$Q_{{tot}}={base_q_tot:,.0f}$, $\\lambda=175.57$",
        xy=(base_q_tot, 175.57), xytext=(base_q_tot + 1100, 470),
        color=INK_SECONDARY, fontsize=8.5,
        arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=0.9),
    )
    for y, txt in ((1137.84, r"$\lambda=m_S=1{,}137.84$   (STRAP marginal)"),
                   (175.57, r"$\lambda=m_W=175.57$   (incineration marginal)"),
                   (0.0, r"$\lambda=0$   (abundant)")):
        ax.text(17_600, y + 26, txt, color=INK_SECONDARY, fontsize=8.5,
                ha="right", va="bottom")

    ax.set_xlabel("Feedstock availability  $Q_{tot}$  [ton/yr]",
                  color=INK_PRIMARY, fontsize=10)
    ax.set_ylabel("Shadow price  $\\lambda$  [USD/ton]",
                  color=INK_PRIMARY, fontsize=10)
    ax.set_title("Linear cost: the equilibrium price is a staircase",
                 color=INK_PRIMARY, fontsize=11.5, pad=10, loc="left")
    ax.set_xlim(-300, 18_300)
    ax.set_ylim(-60, 1_320)

    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return _write_caption(path, FIGL1_CAPTION)


def figL2_allocation(df: pd.DataFrame, path: str | None = None) -> str:
    """Draw the stacked equilibrium allocation against availability.

    Args:
        df:   Sweep results from linear_model.sweep_q_tot.
        path: Output PNG path; defaults to results/figL2_allocation.png.

    Returns:
        The caption string, also written beside the PNG as a .txt file.
    """
    path = path or os.path.join(RESULTS_DIR, "figL2_allocation.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=200, facecolor=SURFACE)
    _style_axes(ax)

    x = df["q_tot_t_per_yr"].to_numpy()
    ax.stackplot(x, *[df[f"q_{k}_t_per_yr"].to_numpy() for k in D.AGENT_NAMES],
                 colors=[SERIES_COLOR[k] for k in D.AGENT_NAMES],
                 labels=[SERIES_LABEL[k] for k in D.AGENT_NAMES],
                 edgecolor=SURFACE, linewidth=0.4, zorder=2)
    ax.plot(x, x, color=INK_MUTED, linewidth=1.1, linestyle=(0, (4, 3)),
            zorder=3, label="All feedstock bought (45$^\\circ$)")

    ax.text(3_000, 1_500, SERIES_LABEL["S"], color=SURFACE, fontsize=9.5,
            ha="center", va="center", fontweight="bold")
    ax.text(12_500, 7_800, SERIES_LABEL["W"], color=INK_SECONDARY, fontsize=9,
            ha="center", va="center")
    ax.text(14_000, 12_400, "landfilled\n(no agent buys)", color=INK_SECONDARY,
            fontsize=8.5, ha="center", va="center")
    ax.text(9_600, 400, "Gasification never enters:  $m_G=-16.69<0$",
            color=INK_SECONDARY, fontsize=8.5, ha="left", va="bottom")

    ax.set_xlabel("Feedstock availability  $Q_{tot}$  [ton/yr]",
                  color=INK_PRIMARY, fontsize=10)
    ax.set_ylabel("Equilibrium throughput  $q_i^{*}$  [ton/yr]",
                  color=INK_PRIMARY, fontsize=10)
    ax.set_title("Linear cost: agents fill in strict merit order",
                 color=INK_PRIMARY, fontsize=11.5, pad=10, loc="left")
    ax.set_xlim(0, 18_000)
    ax.set_ylim(0, 18_000)
    leg = ax.legend(loc="upper left", frameon=False, fontsize=9,
                    labelcolor=INK_SECONDARY)
    for t in leg.get_texts():
        t.set_color(INK_SECONDARY)

    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return _write_caption(path, FIGL2_CAPTION)


def main() -> None:
    """Run the SA-1 sweep, write the CSV, and render both figures."""
    df = L.sweep_q_tot()
    csv = os.path.join(RESULTS_DIR, "linear_sweep_q_tot.csv")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    df.to_csv(csv, index=False)
    p1 = figL1_lambda_staircase(df)
    p2 = figL2_allocation(df)
    print(f"rows={len(df)}  worst KKT residual={df.attrs['worst_kkt_residual']:.3e}")
    print(f"wrote {csv}")
    print("figures written to", RESULTS_DIR)
    assert p1 and p2


if __name__ == "__main__":
    main()
