"""
plot_margins.py -- Figure L0 for the linear-cost report: each firm's net margin.

Net margin m_i (USD per ton of feedstock) is the most a firm can pay for one
more ton and still break even on operations.  The dashed line is the
equilibrium price lambda* at the base case (Q_tot = 8,000 t/yr).

Run:  python plot_margins.py     (writes results/figL0_margins.png)
"""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import linear_model as L  # noqa: E402
from plots import (  # noqa: E402
    GRID,
    INK_PRIMARY,
    INK_SECONDARY,
    LAMBDA_COLOR,
    RESULTS_DIR,
    SERIES_COLOR,
    SURFACE,
)

__all__ = ["figL0_margins"]

_NAMES = {"S": "STRAP", "W": "Incineration", "G": "Gasification"}


def figL0_margins(path: str | None = None) -> str:
    """Draw each firm's net margin per ton with the base-case price marked.

    Args:
        path: Output PNG path; defaults to results/figL0_margins.png.

    Returns:
        The path written.
    """
    path = path or os.path.join(RESULTS_DIR, "figL0_margins.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    agents = L.linear_agents()
    lam = L.solve_linear().lam
    keys = ["S", "W", "G"]
    margins = [agents[k].margin for k in keys]

    fig, ax = plt.subplots(figsize=(7.6, 3.9), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.barh([_NAMES[k] for k in keys[::-1]], margins[::-1],
            color=[SERIES_COLOR[k] for k in keys[::-1]], height=0.52, zorder=3)
    ax.axvline(0, color=INK_SECONDARY, lw=1, zorder=4)
    ax.axvline(lam, color=LAMBDA_COLOR, lw=1.6, ls=(0, (5, 3)), zorder=5)

    for y, v in enumerate(margins[::-1]):
        label = f"{v:,.2f} USD/t".replace("-", "−")
        if v > 0:
            ax.text(v + 18, y, label, va="center", ha="left",
                    color=INK_PRIMARY, fontsize=10)
        else:
            ax.text(v - 18, y, label, va="center", ha="right",
                    color=INK_PRIMARY, fontsize=10)
    ax.text(lam + 12, 2.47, f"Price set by incineration: {lam:,.2f}",
            color=LAMBDA_COLOR, fontsize=9.2, va="center", ha="left")

    ax.set_xlim(-330, 1400)
    ax.set_ylim(-0.6, 2.75)
    ax.set_xlabel("Most the firm can pay for one more ton of feedstock and "
                  "still break even on operations  [USD/ton]",
                  color=INK_SECONDARY, fontsize=8.6)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9.5, length=0)
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.set_title("Who can afford the feedstock?  (net margin per ton, base case)",
                 loc="left", color=INK_PRIMARY, fontsize=11.5, pad=10)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


if __name__ == "__main__":
    print(figL0_margins())
