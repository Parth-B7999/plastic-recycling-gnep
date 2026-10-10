"""
data.py -- Single source of truth for every numerical parameter in the v1 GNEP model.

PROJECT
-------
Generalized Nash Equilibrium among three competing plastic-recycling firms
(S = STRAP, W = Incineration / waste-to-energy, G = Gasification for energy
recovery) that buy post-industrial multilayer film from one shared, limited
feedstock pool.  v1 computes the Variational Equilibrium and the shadow price
`lambda` (USD/ton) on the shared feedstock-availability constraint.

PROVENANCE RULE
---------------
Every constant below carries exactly one of:

    # SOURCE: <where it came from>       -- a real number traced to the paper,
                                           the authors' Julia model, or the
                                           authors' source spreadsheet.
    # ASSUMED -- <justification>         -- a value we had to invent.

Anything tagged ASSUMED is also registered in ASSUMPTIONS and shouted about at
import time and in the final run summary.

PROVENANCE SOURCE KEYS
----------------------
[PAPER]  Munoz-Briones et al., "Decision support for circular economy waste
         management of mixed plastic streams: A case study on post-industrial
         multilayer films."  Tables/Figures cited individually.
         -> Paola_Game_Theory/Paper/Decision_support_for_optimal_waste_management_of_mixed_plastic_streams.pdf

[JULIA]  The authors' own JuMP implementation of the paper's MINLP:
         -> LLM_Opti/Paola new model/PIW Paper Dec 21 w Transportation.ipynb
         Cell numbers are 0-indexed code-cell positions in that notebook.

[XLSX]   The authors' source workbook feeding [JULIA]:
         -> LLM_Opti/Paola new model/RAG-polymer-solubility/src/strap/
            waste_management/Data for model_Scenarios.xlsx
         Several values live in *external-link caches* inside the .xlsx
         (the workbook references other files); those are cited as
         [XLSX ext:<workbook sheet>] and were read out of the cached
         values in xl/externalLinks/externalLink*.xml.

BASE CASE
---------
STRAP energy supply Scenario 1 (grid electricity + imported heat)
Technology location Scenario 1 (in-state and out-of-state facilities).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

__all__ = [
    "AGENTS", "AGENT_NAMES", "ASSUMPTIONS", "AgentData", "Product",
    "SharedConstraint",
    "Q_TOT_BASE", "P_RAW", "C_LF", "CRF", "EMIS_UNIT_SCALE",
    "agent_data", "shared_constraints", "assumption_report",
]

# =============================================================================
# 0.  Assumption registry
# =============================================================================

ASSUMPTIONS: dict[str, str] = {}


def _assume(name: str, value: float, why: str) -> float:
    """Register `name` as an assumed (non-paper) parameter and return `value`.

    Args:
        name:  Parameter name as it appears in this module.
        value: The assumed numeric value (units documented at the call site).
        why:   One-line justification, surfaced in the import-time warning.

    Returns:
        `value`, unchanged.
    """
    ASSUMPTIONS[name] = f"{value!r} -- {why}"
    return value


# =============================================================================
# 1.  Feedstock:  composition, availability, prices of recovered resins
# =============================================================================

Q_TOT_BASE: float = 8_000.0
# SOURCE: [PAPER] Table 6, `F_in` = 8 kton/yr; case-study text.  Units: ton/yr.

F_PE: float = 0.60    # SOURCE: [PAPER] Table 6 / case-study text. mass fraction
F_PET: float = 0.20   # SOURCE: [PAPER] Table 6 / case-study text. mass fraction
F_N6: float = 0.10    # SOURCE: [PAPER] Table 6 / case-study text. mass fraction
F_EVOH: float = 0.10  # SOURCE: [PAPER] Table 6 / case-study text. mass fraction

STRAP_YIELD: float = 0.97
# SOURCE: [PAPER] Table 6, `yield` = 97%; [JULIA] cell 48 (`0.97` factor in Sales).
# Units: ton resin recovered / ton resin present in feed.

P_RESIN_PE: float = 1_173.0
# SOURCE: [PAPER] Table 6, C_p for PE; [JULIA] cell 24 `Cpe=1173`. Units: USD/ton.

P_RESIN_EVOH: float = 8_100.0
# SOURCE: [PAPER] Table 6, C_p for EVOH; [JULIA] cell 24 `Cevoh=8100`. Units: USD/ton.

# PET and N6 are NOT recovered: the paper states no solvent pair can separate a
# PET/N6 film, so that fraction leaves STRAP as residue.
# SOURCE: [PAPER] case-study section ("STRAP can only allow two washing steps").


# =============================================================================
# 2.  Feedstock purchase price and landfill tipping fee (shared market terms)
# =============================================================================

P_RAW: float = _assume(
    "P_RAW", 0.0,
    "Paper hands the single planner its 8 kt/yr feedstock free of charge, so "
    "there is no purchase price to extract. 0 USD/ton keeps v1 consistent with "
    "the paper. NOTE: the authors' own model implicitly values this waste at "
    "PAPER_WASTE_TRANSFER_PRICE = 110 USD/ton (see below), and post-industrial "
    "waste can carry a NEGATIVE price because the generator pays to offload it. "
    "Swept in v1.1 (assumption_sensitivity.sweep_p_raw, SA-1c section 6.3): "
    "d(lambda)/d(p_raw) = -1 exactly for p_raw in [0, 175.57), since p_raw "
    "shifts every agent's margin identically -- the largest lever of the "
    "three SA-1c sweeps.",
)
# Units: USD/ton of mixed feedstock.

PAPER_WASTE_TRANSFER_PRICE: float = 110.0
# SOURCE: [JULIA] cell 47, `Cgas_pw=110  #[USD per ton] data from Kenneth`.
# In the paper's single-planner framing this is REVENUE: the planner *sells*
# leftover plastic waste to incineration / gasification-to-H2 at 110 USD/ton.
# In our multi-agent framing the same number is the price an agent would PAY for
# feedstock, i.e. the natural paper-consistent value of P_RAW. Recorded here for
# a later sweep; NOT used in the v1 base case.  Units: USD/ton.

C_LF: float = _assume(
    "C_LF", 60.0,
    "Landfill tipping fee each agent pays on its own residue. Representative "
    "Wisconsin MSW gate rate. FIXED in v1 (must not depend on residue volume, "
    "which would introduce cost coupling). NOTE: the paper's own landfill cost "
    "is PAPER_C_LF = 7.836 USD/ton, ~8x lower than any real US gate rate.",
)
# Units: USD/ton of residue landfilled.

PAPER_C_LF: float = 7.83599
# SOURCE: [XLSX] sheet 'Othertech w TransportA', cell O2 (OPEX [USD/ton], landfill row).
# Independently confirmed: [PAPER] Table 8 min-emissions (all-landfill) profit is
# -6.27e4 USD/yr on 8,000 ton/yr  =>  7.8375 USD/ton.  Exact match to 8,000 *
# 7.83599 = 62,687.92 USD/yr, which is cell B13/C13 of [XLSX] 'Final Results
# December'.  Retained as a cross-check constant only.  Units: USD/ton.

CRF: float = _assume(
    "CRF", 0.1175,
    "Capital recovery factor for annualizing CAPEX: 10% discount rate, 20-year "
    "life => i(1+i)^n/((1+i)^n-1) = 0.11746. NOTE: the paper annualizes by "
    "simple division by 20 years (PAPER_CRF = 0.05, no discounting) -- see "
    "[XLSX] 'StrapScenario1 Units' column P, formula `StrapScenario1!P<r>/20`.",
)
# Units: 1/yr.

PAPER_CRF: float = 1.0 / 20.0
# SOURCE: [XLSX] 'StrapScenario1 Units'!P2:P28 = 'StrapScenario1'!P<r>/20.
# The paper's undiscounted 20-year straight-line annualization.  Units: 1/yr.


# =============================================================================
# 3.  Emissions units -- DOCUMENTED DISCREPANCY, DO NOT SILENTLY "FIX"
# =============================================================================

EMIS_UNIT_SCALE: float = 1.0
# ASSUMED-FREE: see EMIS_UNIT_NOTE. Multiplies every per-ton emission factor.
# Units: dimensionless.

EMIS_UNIT_NOTE: str = """
EMISSIONS UNIT DISCREPANCY -- RESOLVED, BUT FLAGGED.

The brief flagged that [PAPER] Table 8 reports 15,548.59 "kg CO2-eq/year"
against 8,000 ton/yr of feedstock, i.e. ~1.9 kg CO2 per tonne of plastic --
roughly 1000x below standard plastic-waste LCA values.

Tracing the number to its source resolves this.  Every emission factor in
[XLSX] is carried in the column literally headed "GWP [tonCO2e/ton resin]",
and the landfill factor there is 0.0816 tCO2e/ton.  Multiplying by 8,000 ton/yr
reproduces the paper's landfill figure exactly:

    0.0816 tCO2e/ton * 8,000 ton/yr = 652.80   <-- [PAPER] Table 8, "652.80"

So the underlying data really is in TONNES CO2e, and the paper's table column
header "Emissions [kg CO2-eq/year]" is a LABEL error: those columns are
t CO2-eq/yr.  Corroboration: [PAPER] Table 6 gives the emissions upper bound as
U_g = 21,303.36 *tonCO2eq*, the same order as the Table 8 entries; and the
max-profit pathway at 15,548.59 t CO2e/yr over 8,000 t/yr of feed is
1.94 tCO2e per tonne of plastic -- squarely inside the normal LCA range for
plastic incineration (~2-3 tCO2e/t).

CONSEQUENCE FOR THIS MODEL: all emission factors here are t CO2e per tonne of
feedstock and EMIS_UNIT_SCALE stays 1.0.  No 1000x correction is applied
anywhere.  If you ever need to reproduce the paper's printed table verbatim,
change the *label*, not the number.
""".strip()


# =============================================================================
# 4.  Per-agent technical data
# =============================================================================
#
# --- Residue fractions (rho_i): tonnes to landfill per tonne processed --------

RHO_S: float = 1.0 - STRAP_YIELD * (F_PE + F_EVOH)
# DERIVED from [PAPER] data, not assumed: STRAP recovers only PE and EVOH, at
# 97% yield. rho_S = 1 - 0.97*(0.60 + 0.10) = 0.321.  The PET+N6 fraction plus
# dissolution losses leave as residue.  (The brief's estimate was ~0.32.)
# Units: ton residue / ton feed.

RHO_W: float = _assume(
    "RHO_W", 0.15,
    "Incineration bottom+fly ash fraction. Standard MSW/plastics WTE ash yield "
    "is 10-20% by mass. NOTE: [XLSX] 'Othertech' row 3 records incineration "
    "'Waste to Disposal' as 0.0 ton/ton, which is not physical; we do not use "
    "the paper's zero.",
)
# Units: ton residue / ton feed.

RHO_G: float = _assume(
    "RHO_G", 0.08,
    "Gasification ash/char fraction. Slagging/entrained-flow plastics "
    "gasification leaves less solid residue than grate incineration. NOTE: "
    "[XLSX] 'Othertech' row 5 records gas_er 'Waste to Disposal' as 0.0 "
    "ton/ton, which is not physical; we do not use the paper's zero.",
)
# Units: ton residue / ton feed.

# --- Process emission factors (t CO2e per tonne of feedstock) ----------------

GWP_LANDFILL: float = 0.0864563579568406
# SOURCE: [XLSX] 'Othertech w TransportA'!J2
#   = 0.0816 + 0.328/(1000*0.621371)*9.2
#     (base landfill GWP + truck emission factor * 9.2 miles, Location Sc. 1).
# The no-transport value used in [PAPER] Table 8 is GWP_LANDFILL_NO_TRANSPORT.
# Units: t CO2e / ton landfilled.

GWP_LANDFILL_NO_TRANSPORT: float = 0.0816
# SOURCE: [XLSX] 'Othertech'!J2.  Reproduces Table 8's 652.80 exactly.
# Units: t CO2e / ton landfilled.

# STRAP process GWP is built from three BioSTEAM process blocks, all for
# STRAP energy supply Scenario 1, expressed per tonne of RESIN handled by that
# block, then converted to per tonne of FEED.
_GWP_STRAP_WASH1_PE_PCE: float = 1.132585723
# SOURCE: [XLSX ext:Process_results_C1_P1]!C4 (row 4 = Tetrachloroethylene),
# referenced by 'StrapScenario1'!L4.  Units: t CO2e / ton PE resin recovered.

_GWP_STRAP_WASH2_EVOH_GBL: float = 2.16611774112287
# SOURCE: [XLSX ext:Process_results_C1_E2]!C8 (row 8 = gamma-butyrolactone),
# referenced by 'StrapScenario1'!L28.  Units: t CO2e / ton EVOH resin recovered.

_GWP_STRAP_SHREDDER: float = 0.55746314553726695
# SOURCE: [XLSX ext:Process_results_shredderC1]!C2, referenced by 'Shredder'!K2
# (Scenario 1).  Units: t CO2e / ton resin (workbook scales it on the wash-1
# resin basis, i.e. the PE stream).

_T_PE_RECOVERED: float = Q_TOT_BASE * F_PE * STRAP_YIELD     # 4,656 ton/yr
_T_EVOH_RECOVERED: float = Q_TOT_BASE * F_EVOH * STRAP_YIELD  # 776 ton/yr
# Cross-check: [XLSX ext:'New UBs']!E50 = 4,656,000 kg and !E51 = 776,000 kg are
# the exact scale factors the workbook uses in 'StrapScenario1 Units'!L.

E_PROC_S: float = (
    _GWP_STRAP_WASH1_PE_PCE * _T_PE_RECOVERED
    + _GWP_STRAP_WASH2_EVOH_GBL * _T_EVOH_RECOVERED
    + _GWP_STRAP_SHREDDER * _T_PE_RECOVERED
) / Q_TOT_BASE
# DERIVED from [XLSX] BioSTEAM results, Energy Scenario 1, best pathway
# (Wash 1 = PE/PCE, Wash 2 = EVOH/gamma-butyrolactone).  The shredder is counted
# ONCE (see PAPER_RECONCILIATION_NOTE -- the authors' workbook charges it to
# both washes).  Units: t CO2e / ton feed.

E_PROC_W: float = 2.38
# SOURCE: [XLSX] 'Othertech'!J3 (incineration, no transport).  The Location
# Scenario 1 value including 151 truck-miles is 2.45971 ('Othertech w
# TransportA'!J3 = 2.38 + 0.328/(1000*0.621371)*151).
# Units: t CO2e / ton feed.

E_PROC_G: float = 1.07
# SOURCE: [XLSX ext:Gasification_Technologies]!M2, via 'Othertech'!J5.
# Gasification for energy recovery is sited next to the plastics plant, so its
# transport adder is zero and Location Scenario 1 gives the same 1.07.
# Units: t CO2e / ton feed.


# =============================================================================
# 5.  Per-agent economics
# =============================================================================
#
# --- S = STRAP ---------------------------------------------------------------

REV_S: float = STRAP_YIELD * (F_PE * P_RESIN_PE + F_EVOH * P_RESIN_EVOH)
# DERIVED from [PAPER] Table 6 exactly as [JULIA] cell 48 builds `Sales`:
#   0.97 * (0.60*1173 + 0.10*8100) = 1,468.386 USD per ton of FEED.
# Units: USD / ton feed.

_CAPEX_S_WASH1_PE_PCE: float = 35_957_531.93
# SOURCE: [XLSX ext:Process_results_C1_P1]!K4, via 'StrapScenario1'!P4. USD.
_CAPEX_S_WASH2_EVOH_GBL: float = 14_557_669.26
# SOURCE: [XLSX ext:Process_results_C1_E2]!K8, via 'StrapScenario1'!P28. USD.
_CAPEX_S_SHREDDER: float = 3_130_073.23
# SOURCE: [XLSX ext:Process_results_shredderC1]!G2, via 'Shredder'!O2. USD.

CAPEX_S: float = (
    _CAPEX_S_WASH1_PE_PCE + _CAPEX_S_WASH2_EVOH_GBL + _CAPEX_S_SHREDDER
)
# DERIVED: total installed capital for the paper's best STRAP pathway at
# 8,000 ton/yr, Energy Scenario 1, shredder counted once.  Units: USD.

_OPEX_S_WASH1_PE_PCE: float = 941_556.97
# SOURCE: [XLSX ext:Process_results_C1_P1]!L4, via 'StrapScenario1'!Q4. USD/yr.
_OPEX_S_WASH2_EVOH_GBL: float = 479_709.41
# SOURCE: [XLSX ext:Process_results_C1_E2]!L8, via 'StrapScenario1'!Q28. USD/yr.
_OPEX_S_SHREDDER: float = 1_068_992.28
# SOURCE: [XLSX ext:Process_results_shredderC1]!H2, via 'Shredder'!P2. USD/yr.

OPEX_S_REF: float = (
    _OPEX_S_WASH1_PE_PCE + _OPEX_S_WASH2_EVOH_GBL + _OPEX_S_SHREDDER
)
# DERIVED: total STRAP operating cost at the reference throughput
# Q_REF_S = 8,000 ton/yr, Energy Scenario 1.  = 2,490,258.66 USD/yr
# = 311.28 USD/ton.  Units: USD/yr.

Q_REF_S: float = Q_TOT_BASE
# SOURCE: the BioSTEAM simulations behind OPEX_S_REF were run on the paper's
# 8,000 ton/yr feed basis.  Units: ton/yr.

# --- W = Incineration (waste-to-energy) --------------------------------------

REV_W: float = 259.57
# SOURCE: [JULIA] cell 24, `Cwte=259.57 #($/ton)`, listed by the authors under
# "Cost of the products" beside Cpe and Cevoh -- i.e. the value of the energy
# product per tonne of waste burned.  This is the correct revenue for an agent
# that OPERATES the incinerator.
# CAUTION: the paper's *solved* model does not use Cwte. [JULIA] cell 48 credits
# `we` at Cgas_pw = 110 USD/ton instead, because in the single-planner framing
# the planner SELLS its waste to a third-party incinerator rather than running
# one. Cwte appears in the alternative Sales expression at [JULIA] cell 66.
# Units: USD / ton feed.

OPEX_W_PER_TON: float = _assume(
    "OPEX_W_PER_TON", 75.0,
    "Incineration operating cost. THE PAPER HAS NO VALUE FOR THIS: [XLSX] "
    "'Othertech'!O3 records incineration OPEX as 0 and CAPEX as 0, because the "
    "paper models incineration as a third-party off-take market (it sells waste "
    "at 110 USD/ton), never as an owned facility. 75 USD/ton is a mid-range US "
    "MSW waste-to-energy O&M cost (typical 60-90 USD/ton).",
)
# Units: USD / ton feed.

CAPEX_W: float = _assume(
    "CAPEX_W", 30_000_000.0,
    "Incineration installed capital at CAP_W = 4,000 ton/yr. Not in the paper "
    "(see OPEX_W_PER_TON). ~7,500 USD per annual tonne, consistent with "
    "small-scale WTE. Affects viability only, never the equilibrium q*.",
)
# Units: USD.

# --- G = Gasification for energy recovery ------------------------------------

_GAS_ER_HEAT_YIELD: float = 583.33      # SOURCE: [JULIA] cell 47. MJ/tonne
_GAS_ER_ELEC_YIELD: float = 724.3693    # SOURCE: [JULIA] cell 47. kWh/tonne
_GAS_ER_PRICE_HEAT: float = 0.13        # SOURCE: [JULIA] cell 47. USD/MJ
_GAS_ER_PRICE_ELEC: float = 0.0996      # SOURCE: [JULIA] cell 47. USD/kWh

REV_G: float = (
    _GAS_ER_HEAT_YIELD * _GAS_ER_PRICE_HEAT
    + _GAS_ER_ELEC_YIELD * _GAS_ER_PRICE_ELEC
)
# DERIVED exactly as [JULIA] cell 47 computes `Cgas_er` = 147.98 USD/ton.
# CAUTION: _GAS_ER_PRICE_HEAT = 0.13 USD/MJ is ~130 USD/GJ, an order of
# magnitude above any industrial heat price (typically 5-15 USD/GJ). We keep the
# authors' number because it is what produced the published results, but see
# G_REVENUE_MULTIPLIER.  Units: USD / ton feed.

G_REVENUE_MULTIPLIER: float = 1.0
# Tunable knob on REV_G, default 1.0 = the paper's own value. Exposed because
# agent G's margin is thin (see VIABILITY_NOTE); NOT swept in v1.

OPEX_G_PER_TON: float = 159.86712271878616
# SOURCE: [XLSX ext:Gasification_Technologies]!X2, via 'Othertech'!O5.
# Units: USD / ton feed.

_CAPEX_G_COEFF: float = 15_749.6
_CAPEX_G_EXPONENT: float = 0.6
# DERIVED, and validated at four independent points. The authors hard-code
# gasification-for-energy-recovery annualized CAPEX at four capacities in
# [JULIA] cell 48 and [XLSX] 'Othertech'!N5:
#     8,000 t/yr -> 3,460,308 USD/yr   ([XLSX ext:Gasification_Technologies]!T2*1e6)
#     7,200 t/yr -> 3,248,331 USD/yr   ([JULIA] cell 48, coefficient on `t`)
#     3,200 t/yr -> 1,996,874 USD/yr   ([JULIA] cell 48, coefficient on `p`)
#     2,400 t/yr -> 1,680,303 USD/yr   ([JULIA] cell 48, coefficient on `z`)
# Fitting CAPEX = A * F^n to the 3,200 / 7,200 pair gives n = 0.6000 and
# A = 15,749.6; that fit then reproduces the 8,000 t/yr point to 0.03% and the
# 2,400 t/yr point to 0.07%. A textbook six-tenths scaling rule.
# Units: USD/yr when F is in ton/yr (the column is headed "CAPEX [USD/yr]", so
# this is ALREADY annualized by the authors -- see ACC_G below).


def capex_g_annualized(capacity_tpy: float) -> float:
    """Annualized CAPEX of gasification-for-energy-recovery at a given capacity.

    Args:
        capacity_tpy: Nameplate capacity, ton/yr.

    Returns:
        Annualized capital charge, USD/yr.  Already annualized by the authors
        (their column is "CAPEX [USD/yr]"), so CRF is NOT applied on top.
    """
    return _CAPEX_G_COEFF * capacity_tpy ** _CAPEX_G_EXPONENT


# =============================================================================
# 6.  Capacities
# =============================================================================

CAP_S: float = _assume(
    "CAP_S", 6_000.0,
    "STRAP nameplate. Chosen with CAP_W and CAP_G so total capacity 14,000 > "
    "Q_TOT_BASE 8,000, making the shared constraint BIND at base case and "
    "lambda > 0. [PAPER] location Scenario 3 notes a shared STRAP facility "
    "sized at 20 kton/yr, so 6 kton/yr is a conservative single-firm plant.",
)  # ton/yr

CAP_W: float = _assume(
    "CAP_W", 4_000.0, "Incineration nameplate; see CAP_S.",
)  # ton/yr

CAP_G: float = _assume(
    "CAP_G", 4_000.0, "Gasification nameplate; see CAP_S.",
)  # ton/yr

OPEX_CURVATURE_RATIO: float = _assume(
    "OPEX_CURVATURE_RATIO", 1.20,
    "OPEX per ton at full capacity divided by OPEX per ton at 50% capacity. "
    "Sets the quadratic curvature b_i that makes each agent's program strictly "
    "concave (=> unique variational equilibrium, smooth lambda). Physically an "
    "off-design penalty: specific energy use and solvent make-up worsen as "
    "throughput approaches nameplate.",
)  # dimensionless

CAPEX_SCALE_EXPONENT_S: float = _assume(
    "CAPEX_SCALE_EXPONENT_S", 0.6,
    "Six-tenths-rule scaling exponent for HOW STRAP's annualized capital charge "
    "would move with a DIFFERENT capacity, ACC_S(Cap) = ACC_S_base * "
    "(Cap/Cap_S_base)^n. Added for SA-1b (v1.1), used only by "
    "capacity_sensitivity.py -- it does NOT affect the base-case ACC_S, which "
    "stays CRF*CAPEX_S regardless of this constant. Unlike gasification's "
    "exponent (_CAPEX_G_EXPONENT = 0.6), there is no authors' data to fit this "
    "from -- 0.6 is the standard chemical-engineering six-tenths rule, used as a "
    "default and swept over {0.6, 0.8, 1.0} in SA-1b to bound the conclusion.",
)  # dimensionless

CAPEX_SCALE_EXPONENT_W: float = _assume(
    "CAPEX_SCALE_EXPONENT_W", 0.6,
    "Same six-tenths-rule default as CAPEX_SCALE_EXPONENT_S, for incineration. "
    "See that entry for the full justification.",
)  # dimensionless


# =============================================================================
# 7.  OPEX calibration:  OPEX_i(q) = a_i*q + 0.5*b_i*q^2
# =============================================================================

def calibrate_opex(
    opex_ref: float, q_ref: float, cap: float, ratio: float = OPEX_CURVATURE_RATIO
) -> tuple[float, float]:
    """Calibrate the convex quadratic OPEX curve for one agent.

    The curve is  OPEX(q) = a*q + 0.5*b*q^2  [USD/yr], so the *average* cost is
    OPEX(q)/q = a + 0.5*b*q [USD/ton] and the *marginal* cost is a + b*q.

    Two conditions pin down (a, b):

    1. CURVATURE.  Average cost at nameplate is `ratio` times average cost at
       half nameplate:
           a + 0.5*b*Cap = ratio * (a + 0.25*b*Cap)
       For ratio = 1.2 this collapses to the clean relation  a = b*Cap,
       i.e.  b = a/Cap.

    2. LEVEL.  Total OPEX reproduces the reference cost at the reference
       throughput:
           a*q_ref + 0.5*b*q_ref^2 = opex_ref
       Substituting b = a/Cap:
           a = opex_ref / ( q_ref * (1 + 0.5*q_ref/Cap) )

    NOTE ON q_ref > cap:  for STRAP the reference throughput is the paper's
    8,000 ton/yr feed basis while CAP_S is 6,000 ton/yr. That is intentional and
    harmless -- the cost curve is a smooth function defined for all q >= 0, and
    the paper's OPEX number genuinely corresponds to 8,000 ton/yr. Calibrating
    at the paper's own basis is the honest choice; the capacity bound is then
    imposed separately as the private constraint q_S <= CAP_S.

    Args:
        opex_ref: Total operating cost at `q_ref`, USD/yr.
        q_ref:    Reference throughput the cost was measured at, ton/yr.
        cap:      Nameplate capacity used for the curvature rule, ton/yr.
        ratio:    Average-cost ratio (full capacity : half capacity).

    NOTE ON THE LOWER BOUND (added for SA-1c, v1.1): ratio = 1.0 is a valid,
    non-degenerate limit -- average cost at full capacity equals average cost at
    half, i.e. purely LINEAR OPEX with b = 0.  The formula below is continuous
    there (b_over_a -> 0, a -> opex_ref/q_ref), so the bound is <=, not <.  This
    boundary is exercised by the OPEX_CURVATURE_RATIO sweep in
    capacity_sensitivity.py, which needs the ratio = 1.0 endpoint to locate where
    m_G changes sign.

    Returns:
        (a, b) with a in USD/ton and b in USD/ton^2.
    """
    if not 1.0 <= ratio < 2.0:
        raise ValueError(f"OPEX curvature ratio must lie in [1, 2), got {ratio}")
    # Condition 1:  a*(ratio - 1) = b*Cap*(0.5 - 0.25*ratio)  =>  b/a is fixed.
    b_over_a = (ratio - 1.0) / (cap * (0.5 - 0.25 * ratio))
    # From condition 2:  a*q_ref + 0.5*(b_over_a*a)*q_ref^2 = opex_ref
    a = opex_ref / (q_ref * (1.0 + 0.5 * b_over_a * q_ref))
    b = b_over_a * a
    return a, b


# =============================================================================
# 8.  Agent assembly
# =============================================================================

@dataclass(frozen=True)
class Product:
    """One saleable output stream k of an agent.

    Attributes:
        key:   Short identifier.
        label: Human-readable name.
        price: P_k, USD per unit of product.
        eta:   eta_ik, units of product per ton of feedstock processed.
        unit:  Physical unit of the product.
    """

    key: str
    label: str
    price: float
    eta: float
    unit: str


@dataclass(frozen=True)
class AgentData:
    """Complete parameter set for one strategic agent.

    Attributes:
        key:        Short identifier, one of "S", "W", "G".
        name:       Human-readable technology name.
        cap:        Private capacity bound Cap_i, ton/yr.
        products:   Saleable outputs; revenue = sum_k price_k * eta_k.
        revenue:    Product revenue per tonne of feedstock, USD/ton
                    (= sum_k P_k * eta_ik; kept as a field so it is visible in
                    one place, but always equal to `gross_revenue`).
        a:          Linear OPEX coefficient, USD/ton.
        b:          Quadratic OPEX curvature, USD/ton^2 (strict concavity).
        rho:        Residue fraction sent to landfill, ton residue/ton feed.
        e_proc:     Process emission factor, t CO2e/ton feed.
        acc:        Annualized capital charge ACC_i, USD/yr (constant; does NOT
                    affect the equilibrium q*, only economic viability).
        opex_ref:   Reference total OPEX used for calibration, USD/yr.
        q_ref:      Reference throughput for that OPEX, ton/yr.
    """

    key: str
    name: str
    cap: float
    products: tuple[Product, ...]
    revenue: float
    a: float
    b: float
    rho: float
    e_proc: float
    acc: float
    opex_ref: float
    q_ref: float

    @property
    def gross_revenue(self) -> float:
        """sum_k P_k * eta_ik, USD per ton of feedstock."""
        return sum(pr.price * pr.eta for pr in self.products)

    @property
    def margin(self) -> float:
        """Net linear margin m_i, USD/ton.

        m_i = sum_k P_k*eta_ik - a_i - p_raw - c_lf*rho_i

        This is the constant that drives the whole equilibrium: the interior
        best response is q_i = (m_i - lambda)/b_i.
        """
        return self.revenue - self.a - P_RAW - C_LF * self.rho

    @property
    def unconstrained_demand(self) -> float:
        """Throughput the agent would choose at lambda = 0, ton/yr.

        q_i(0) = clip(m_i / b_i, 0, Cap_i).  Summing this over agents gives the
        abundance threshold at which lambda hits exactly zero.
        """
        return min(self.cap, max(0.0, self.margin / self.b))

    @property
    def wants_more_than_nameplate(self) -> bool:
        """Would this agent process more than nameplate at a zero feedstock price?

        True iff m_i / b_i >= Cap_i.

        *** THIS IS A STATIC STRUCTURAL PROPERTY, NOT AN EQUILIBRIUM STATE. ***

        It depends only on the agent's own cost curve and capacity, and knows
        nothing about lambda, about the other agents, or about Q_tot.  An agent
        for which this is True may still sit strictly INSIDE its capacity at
        equilibrium -- incineration does exactly that at the base case
        (q_W = 2,000 of Cap_W = 4,000, mu_W = 0) while this property returns
        True, because it would want 16,046 t/yr at lambda = 0.

        For the equilibrium state of an agent use Equilibrium.agent_state(),
        which classifies from the SOLVED lambda.  Conflating the two is what
        made Table 1 report incineration as capacity-constrained and hide the
        fact that it is the price-setter.

        Returns:
            True if the capacity bound, rather than the agent's own margin,
            would limit it at lambda = 0.
        """
        return self.margin / self.b >= self.cap

    @property
    def e_total(self) -> float:
        """Total emission factor including residue landfilling, t CO2e/ton feed."""
        return EMIS_UNIT_SCALE * (self.e_proc + self.rho * GWP_LANDFILL)


PRODUCTS_S: tuple[Product, ...] = (
    Product("PE", "Recycled PE resin", P_RESIN_PE, STRAP_YIELD * F_PE, "ton"),
    Product("EVOH", "Recycled EVOH resin", P_RESIN_EVOH, STRAP_YIELD * F_EVOH, "ton"),
)
# SOURCE: [PAPER] Table 6 prices; eta = yield * mass fraction, exactly the Sales
# expression of [JULIA] cell 48.  eta_S,PE = 0.582, eta_S,EVOH = 0.097 ton/ton.

PRODUCTS_W: tuple[Product, ...] = (
    Product("energy", "Electricity + heat from waste-to-energy", REV_W, 1.0,
            "ton feed"),
)
# The paper carries incineration output as a lumped value per tonne burned
# (Cwte), not as separate physical streams, so eta = 1 and the price is the
# per-ton product value.  See REV_W for the provenance caution.

PRODUCTS_G: tuple[Product, ...] = (
    Product("heat", "Exported heat", _GAS_ER_PRICE_HEAT,
            _GAS_ER_HEAT_YIELD * G_REVENUE_MULTIPLIER, "MJ"),
    Product("electricity", "Exported electricity", _GAS_ER_PRICE_ELEC,
            _GAS_ER_ELEC_YIELD * G_REVENUE_MULTIPLIER, "kWh"),
)
# SOURCE: [JULIA] cell 47.  Here the two physical streams ARE resolved, so
# y_G,heat and y_G,elec are real MJ/yr and kWh/yr at equilibrium.


def _build_agents() -> dict[str, AgentData]:
    a_s, b_s = calibrate_opex(OPEX_S_REF, Q_REF_S, CAP_S)
    a_w, b_w = calibrate_opex(OPEX_W_PER_TON * CAP_W, CAP_W, CAP_W)
    a_g, b_g = calibrate_opex(OPEX_G_PER_TON * CAP_G, CAP_G, CAP_G)
    return {
        "S": AgentData(
            key="S", name="STRAP (solvent-targeted recovery and precipitation)",
            cap=CAP_S, products=PRODUCTS_S, revenue=REV_S, a=a_s, b=b_s, rho=RHO_S, e_proc=E_PROC_S,
            acc=CRF * CAPEX_S, opex_ref=OPEX_S_REF, q_ref=Q_REF_S,
        ),
        "W": AgentData(
            key="W", name="Incineration (waste-to-energy)",
            cap=CAP_W, products=PRODUCTS_W, revenue=REV_W, a=a_w, b=b_w, rho=RHO_W, e_proc=E_PROC_W,
            acc=CRF * CAPEX_W, opex_ref=OPEX_W_PER_TON * CAP_W, q_ref=CAP_W,
        ),
        "G": AgentData(
            key="G", name="Gasification for energy recovery",
            cap=CAP_G, products=PRODUCTS_G,
            revenue=REV_G * G_REVENUE_MULTIPLIER, a=a_g, b=b_g,
            rho=RHO_G, e_proc=E_PROC_G,
            acc=capex_g_annualized(CAP_G),  # already annualized by the authors
            opex_ref=OPEX_G_PER_TON * CAP_G, q_ref=CAP_G,
        ),
    }


AGENTS: dict[str, AgentData] = _build_agents()
AGENT_NAMES: tuple[str, ...] = ("S", "W", "G")


def agent_data() -> dict[str, AgentData]:
    """Return the agent parameter dictionary (fresh dict, shared AgentData)."""
    return dict(AGENTS)


# =============================================================================
# 9.  Shared constraints -- a LIST, so a future emissions cap just appends here
# =============================================================================

@dataclass(frozen=True)
class SharedConstraint:
    """One coupling constraint shared by all agents: sum_i coeff_i * q_i <= rhs.

    Attributes:
        key:        Identifier used as the multiplier's name.
        label:      Human-readable description for tables and figures.
        coeff:      Per-agent coefficient on q_i.
        rhs:        Right-hand side.
        unit:       Units of the associated multiplier, for reporting.
    """

    key: str
    label: str
    coeff: dict[str, float]
    rhs: float
    unit: str


def shared_constraints(q_tot: float = Q_TOT_BASE) -> list[SharedConstraint]:
    """Build the list of shared (coupling) constraints for the VE.

    v1 has exactly ONE: feedstock availability.  The MCP assembly iterates over
    this list, so adding a second coupling constraint later (e.g. a system-wide
    emissions cap with its own multiplier) requires no restructuring -- append
    a SharedConstraint here.  DO NOT add a second constraint in v1.

    Args:
        q_tot: Total feedstock available, ton/yr.

    Returns:
        List of SharedConstraint, length 1 in v1.
    """
    return [
        SharedConstraint(
            key="lambda",
            label="Shared feedstock availability  sum_i q_i <= Q_tot",
            coeff={k: 1.0 for k in AGENT_NAMES},
            rhs=q_tot,
            unit="USD/ton",
        )
    ]


# =============================================================================
# 10.  Paper cross-check constants and reconciliation notes
# =============================================================================

PAPER_MAX_PROFIT_E1: float = 7.551141964e6
# SOURCE: [PAPER] Table 8 ("7.55 x 10^6"); exact figure from [XLSX]
# 'Final Results December'!I13.  Pathway: STRAP1(PE,PCE) + STRAP2(EVOH,GBL) +
# Gasification for H2.  Units: USD/yr.

PAPER_MAX_CE_PROFIT_E1: float = 7.240041162e6
# SOURCE: [PAPER] Table 8 ("7.24 x 10^6"); [XLSX] 'Final Results December'!K13.
# Pathway: STRAP1(PE,PCE) + STRAP2(EVOH,pyridazine) + Landfill.  Units: USD/yr.

PAPER_MAX_PROFIT_EMISSIONS_E1: float = 15_548.5860209036
# SOURCE: [PAPER] Table 8; [XLSX] 'Final Results December'!I14.
# Units: t CO2e/yr (see EMIS_UNIT_NOTE -- the paper labels this "kg").

PAPER_LANDFILL_ONLY_PROFIT: float = -62_687.92
# SOURCE: [PAPER] Table 8 min-emissions row ("-6.27 x 10^4"); [XLSX]
# 'Final Results December'!C13 = -8000*7.83599.  Units: USD/yr.

PAPER_RECONCILIATION_NOTE: str = """
RECONCILING OUR PER-UNIT NUMBERS WITH THE PAPER'S PATHWAY TOTALS.

What reconciles exactly
-----------------------
* Landfill.  8,000 t/yr * 7.83599 USD/ton = 62,687.92 USD/yr, matching Table 8's
  min-emissions profit of -6.27e4 to the cent.
* Landfill emissions.  0.0816 tCO2e/ton * 8,000 = 652.80, matching Table 8.
* Solvent delta.  Table 8's max-profit (GBL) and max-CE (pyridazine) rows differ
  by 3.11e5 USD/yr, of which the pathway change accounts for most; the pure
  solvent swap computed from the workbook,
      (14,937,682.80 - 14,557,669.26)/20 + (486,717.81 - 479,709.41)
      = 26,009 USD/yr,
  agrees with the 27,194 USD/yr implied by the paper's 3-significant-figure
  profits. This confirms both the per-wash data AND the /20 annualization.
* Gasification CAPEX scaling.  A six-tenths rule fitted to two of the authors'
  hard-coded capacities reproduces the other two to <0.1%.

What does NOT reconcile exactly
-------------------------------
Rebuilding Table 8's max-profit total from the workbook's own per-wash CAPEX and
OPEX does not land on 7.551e6 under any single consistent convention:

  * shredder charged to BOTH washes (the workbook's literal formula)
        -> 5,613,069.68 USD/yr and 19,786.29 tCO2e/yr.
        These two numbers appear VERBATIM in [XLSX] 'Final Results December'
        cells B28 and B29, so this is the authors' own full-accounting figure.
  * shredder charged once
        -> 6,838,566 USD/yr.
  * wash-1 + shredder CAPEX only, all three OPEX lines
        -> 7,566,449 USD/yr, i.e. within 0.2% of the reported 7.551e6.

So the published 7.55e6 appears to omit the wash-2 capital charge. We do NOT
attempt to reproduce the paper's pathway bookkeeping. This model uses the
per-unit BioSTEAM process data directly, which is unambiguous, and counts the
shredder once. Verification test 10 therefore compares ORDER OF MAGNITUDE only,
and reports the ratio, exactly as the brief requires.
""".strip()


# =============================================================================
# 11.  Import-time assumption warning
# =============================================================================

def assumption_report() -> str:
    """Return a formatted, loud listing of every parameter that was assumed."""
    lines = [
        "=" * 78,
        "PARAMETERS THAT FELL BACK TO AN ASSUMPTION (results below rest on these)",
        "=" * 78,
    ]
    for name, why in ASSUMPTIONS.items():
        lines.append(f"  * {name}")
        for chunk in _wrap(why, 72):
            lines.append(f"        {chunk}")
    lines.append("=" * 78)
    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    """Minimal greedy word wrap (avoids a textwrap import in a data module)."""
    out: list[str] = []
    line = ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


VIABILITY_NOTE: str = """
AGENT VIABILITY AT THE PAPER'S OWN DATA -- READ THIS.

Gasification for energy recovery (agent G) cannot cover its own operating cost
at nameplate from energy sales alone:

    revenue  REV_G          = 147.98 USD/ton   ([JULIA] cell 47)
    average OPEX at Cap_G   = 159.87 USD/ton   ([XLSX] Gasification_Technologies!X2)
                              --------------
    average margin          = -11.89 USD/ton   before residue disposal and feedstock

This is consistent with the paper itself: gasification-for-energy-recovery is
never chosen in ANY reported optimal solution (Tables 8-12 always pick
gasification-to-H2, incineration, or landfill).

Because our OPEX curve is convex, G's MARGINAL cost at low throughput is below
its average cost at nameplate, so G still has a positive linear margin m_G and
does enter the equilibrium once feedstock is abundant -- it simply operates well
below nameplate. That is an economically meaningful outcome, not a modelling
artifact, and it is what produces the merit order in Figure 2.

Two of the authors' inputs behind REV_G look dimensionally suspect and are
flagged rather than silently corrected:
  * price_heat = 0.13 USD/MJ  (= 130 USD/GJ; industrial heat is 5-15 USD/GJ)
  * products_heat = 583.33 MJ/tonne (plastics carry 30-40 GJ/tonne)
Correcting either one makes G LESS viable, not more, so the qualitative
conclusion is robust. G_REVENUE_MULTIPLIER is exposed for exploration but is
NOT swept in v1.
""".strip()


warnings.warn(
    "\n" + assumption_report() + "\n" + VIABILITY_NOTE + "\n",
    stacklevel=2,
)


if __name__ == "__main__":  # pragma: no cover
    import sys

    def _p(*a: object) -> None:
        print(*a, file=sys.stdout)

    _p("\n" + "=" * 78)
    _p("v1 GNEP PARAMETER EXTRACTION -- BASE CASE")
    _p("  STRAP energy supply Scenario 1, technology location Scenario 1")
    _p("=" * 78)
    _p(f"  Q_tot (base)          {Q_TOT_BASE:>14,.1f}  ton/yr")
    _p(f"  p_raw                 {P_RAW:>14,.2f}  USD/ton      [ASSUMED]")
    _p(f"  c_lf                  {C_LF:>14,.2f}  USD/ton      [ASSUMED]")
    _p(f"  CRF                   {CRF:>14,.5f}  1/yr         [ASSUMED]")
    _p(f"  EMIS_UNIT_SCALE       {EMIS_UNIT_SCALE:>14,.3f}  -")
    _p("")
    hdr = (f"  {'':2s} {'Cap':>8s} {'revenue':>9s} {'a_i':>9s} {'b_i':>11s} "
           f"{'m_i':>10s} {'rho':>6s} {'e_i':>7s} {'ACC':>12s}")
    _p(hdr)
    _p(f"  {'':2s} {'ton/yr':>8s} {'USD/t':>9s} {'USD/t':>9s} {'USD/t^2':>11s} "
       f"{'USD/t':>10s} {'t/t':>6s} {'tCO2/t':>7s} {'USD/yr':>12s}")
    _p("  " + "-" * 82)
    for k in AGENT_NAMES:
        ag = AGENTS[k]
        _p(f"  {ag.key:2s} {ag.cap:>8,.0f} {ag.revenue:>9,.2f} {ag.a:>9,.2f} "
           f"{ag.b:>11.6f} {ag.margin:>10,.2f} {ag.rho:>6.3f} "
           f"{ag.e_total:>7.3f} {ag.acc:>12,.0f}")
    _p("")
    for k in AGENT_NAMES:
        ag = AGENTS[k]
        kind = ("would exceed nameplate at lambda=0"
                if ag.wants_more_than_nameplate else "margin-limited below nameplate")
        _p(f"  {ag.key}: {ag.name}")
        _p(f"      demand at lambda=0 = min(Cap, m/b) = {ag.unconstrained_demand:,.1f} ton/yr"
           f"   ({kind})")
    tot = sum(AGENTS[k].unconstrained_demand for k in AGENT_NAMES)
    _p("")
    _p(f"  Aggregate unconstrained demand = {tot:,.1f} ton/yr")
    _p(f"  => shared constraint BINDS at Q_tot = {Q_TOT_BASE:,.0f} "
       f"({'yes' if tot > Q_TOT_BASE else 'NO'}), so lambda "
       f"{'> 0' if tot > Q_TOT_BASE else '= 0'} at base case.")
    _p(f"  => lambda hits exactly zero at Q_tot = {tot:,.1f} ton/yr.")
    _p("")
    _p(EMIS_UNIT_NOTE)
    _p("")
    _p(VIABILITY_NOTE)
    _p("")
    _p(PAPER_RECONCILIATION_NOTE)
    _p("")
    _p(assumption_report())
