"""
data.py -- inputs for the four-firm feedstock-competition game.

Four firms compete to buy one shared pool of post-industrial multilayer film:

    gas     gasification for hydrogen
    ccs     gasification for hydrogen + carbon capture (CCS)
    strap   STRAP (its residue is landfilled; the landfill cost is already inside
            the OPEX figure Paola supplied, so no separate landfill fee is applied)
    inc     incineration

Nothing from gasification or incineration goes to landfill.  Waste that no firm
buys is landfilled, but that costs the firms nothing and is not an agent.

All economics are per ton of feedstock and CONSTANT in throughput (linear cost),
as supplied by Paola.  The net margin of a firm is

    m_i = revenue_i - opex_i - p_raw          [USD/ton]

CCS earns the U.S. Section 45Q carbon-capture tax credit, which Paola puts at
270 USD per ton of feed; it is added to the revenue of the CCS firm.  Each plant
also carries an annualized capital charge (USD/yr, for an 8,000 t/yr plant).  It
is a constant, so it enters profit but not the optimal throughput:

    profit_i = m_i * q_i - ACC_i

Provenance tags
    PAOLA    number supplied by Paola (the table of Oct 2026)
    ASSUMED  our default, to be confirmed with Paola
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Shared parameters
# ---------------------------------------------------------------------------
Q_TOT_BASE = 20_000.0   # t/yr  ASSUMED: regional pool larger than any one plant,
                        #       so that firms genuinely compete (Paola to confirm)
P_RAW = 0.0             # USD/t ASSUMED: the generator gives the waste away
CCS_CREDIT = 270.0      # USD per ton of feed, PAOLA: 45Q credit for the CCS plant


@dataclass(frozen=True)
class Agent:
    """One firm's economics.  Units: USD per ton of feed; cap in t/yr."""

    key: str
    name: str
    revenue: float
    opex: float
    cap: float
    source: str
    acc: float | None = None   # annualized capital, USD/yr (None = not supplied)

    @property
    def margin(self) -> float:
        """Net margin m_i = revenue - opex - p_raw (reads P_RAW at call time)."""
        return self.revenue - self.opex - P_RAW


# Capacities: each plant at the scale its cost was quoted for.
#   gas, ccs, strap : 8,000 t/yr (the scale of Paola's cost table)
#   inc             : 12,800 t/yr = 12.8% plastic share of a 100,000 t/yr plant
AGENTS: dict[str, Agent] = {
    "gas": Agent("gas", "Gasification", 1635.0, 224.9986765, 8_000.0,
               "PAOLA revenue/OPEX/capex; capacity ASSUMED", acc=5_999_788.24),
    "ccs": Agent("ccs", "Gasification + CCS", 1635.0 + CCS_CREDIT, 494.234432, 8_000.0,
               "PAOLA revenue (incl. 45Q credit)/OPEX/capex; capacity ASSUMED",
               acc=7_077_509.116),
    "strap": Agent("strap", "STRAP", 1468.386, 535.4271538, 8_000.0,
               "PAOLA revenue/OPEX (OPEX includes landfill)/capex; capacity ASSUMED",
               acc=6_314_455.733),
    "inc": Agent("inc", "Incineration", 259.5664195, 138.0970614, 12_800.0,
               "PAOLA revenue/OPEX; capex NOT supplied; capacity ASSUMED"),
}
KEYS = list(AGENTS)           # ["gas", "ccs", "strap", "inc"]
