# v1 GNEP — Parameter extraction notes

**Status:** Step 8 of the brief. `Code/data.py` is written; **no model code yet**.
Check the numbers below against the paper before I build `agents.py` / `gnep_mcp.py`.

**Base case:** STRAP energy supply Scenario 1 (grid electricity + imported heat),
technology location Scenario 1.

---

## 0. The big finding: most "must be assumed" parameters were recoverable

The brief expected the standalone incineration / gasification margins to be a hard
data gap. They largely aren't — **the authors' own model and its source
spreadsheet are sitting in your project**, and they contain the per-unit numbers
the paper never prints:

| Source key | File |
|---|---|
| `[PAPER]` | `Paola_Game_Theory/Paper/Decision_support_..._mixed_plastic_streams.pdf` |
| `[JULIA]` | `LLM_Opti/Paola new model/PIW Paper Dec 21 w Transportation.ipynb` (JuMP/Gurobi) |
| `[XLSX]`  | `LLM_Opti/Paola new model/RAG-polymer-solubility/src/strap/waste_management/Data for model_Scenarios.xlsx` |

Caveat on `[XLSX]`: it is a formula workbook whose cached values were stripped, so
`pandas`/`openpyxl` return blanks. The real numbers live in the **external-link
caches** (`xl/externalLinks/externalLink*.xml`) inside the `.xlsx`; I read them out
of the raw XML. Anything tagged `[XLSX ext:<sheet>]` in `data.py` came from there.

Net effect: **6 of the 10 parameters the brief listed as "must be assumed" are now
real numbers**, and one (`rho_S`) is derived exactly.

---

## 1. Straight from the paper — verify these first

| Parameter | Value | Units | Provenance |
|---|---|---|---|
| `Q_TOT_BASE` | 8,000 | ton/yr | Table 6, `F_in` |
| `F_PE / F_PET / F_N6 / F_EVOH` | 0.60 / 0.20 / 0.10 / 0.10 | – | Table 6 |
| `STRAP_YIELD` | 0.97 | – | Table 6; `[JULIA]` cell 48 |
| `P_RESIN_PE` | 1,173 | USD/ton | Table 6; `[JULIA]` cell 24 `Cpe` |
| `P_RESIN_EVOH` | 8,100 | USD/ton | Table 6; `[JULIA]` cell 24 `Cevoh` |

Derived STRAP revenue, exactly as `[JULIA]` cell 48 builds `Sales`:

```
REV_S = 0.97 * (0.60*1173 + 0.10*8100) = 1,468.386 USD per ton of FEED
```

PET and N6 are not recovered (no solvent pair separates a PET/N6 film), so they
leave as residue.

---

## 2. Recovered from the authors' model — *not* assumed

| Parameter | Value | Units | Provenance |
|---|---|---|---|
| STRAP wash-1 CAPEX (PE / PCE) | 35,957,531.93 | USD | `[XLSX ext:Process_results_C1_P1]!K4` |
| STRAP wash-2 CAPEX (EVOH / γ-butyrolactone) | 14,557,669.26 | USD | `[XLSX ext:Process_results_C1_E2]!K8` |
| Shredder CAPEX (Scenario 1) | 3,130,073.23 | USD | `[XLSX ext:Process_results_shredderC1]!G2` |
| **`CAPEX_S` (total)** | **53,645,274.42** | USD | sum, shredder counted once |
| STRAP wash-1 OPEX | 941,556.97 | USD/yr | `…C1_P1!L4` |
| STRAP wash-2 OPEX | 479,709.41 | USD/yr | `…C1_E2!L8` |
| Shredder OPEX | 1,068,992.28 | USD/yr | `…shredderC1!H2` |
| **`OPEX_S_REF` @ 8,000 t/yr** | **2,490,258.66** | USD/yr (= 311.28 USD/t) | sum |
| `REV_W` (incineration product value) | 259.57 | USD/ton | `[JULIA]` cell 24 `Cwte` |
| `REV_G` (gas. energy recovery) | 147.98 | USD/ton | `[JULIA]` cell 47 `Cgas_er` |
| `OPEX_G_PER_TON` | 159.867 | USD/ton | `[XLSX ext:Gasification_Technologies]!X2` |
| `E_PROC_W` | 2.38 | tCO₂e/ton | `[XLSX] 'Othertech'!J3` |
| `E_PROC_G` | 1.07 | tCO₂e/ton | `[XLSX ext:Gasification_Technologies]!M2` |
| `GWP_LANDFILL` (Loc. Sc. 1) | 0.086456 | tCO₂e/ton | `'Othertech w TransportA'!J2` |
| `PAPER_C_LF` | 7.83599 | USD/ton | `'Othertech'!O2` |

**STRAP emission factor, derived:**
```
E_PROC_S = (1.132586*4656 + 2.166118*776 + 0.557463*4656) / 8000
         = 1.1937 tCO2e per ton of FEED
```
(1.1326 = wash-1 PE/PCE, 2.1661 = wash-2 EVOH/GBL, 0.5575 = shredder, all per ton
of *resin*; 4,656 and 776 t/yr are the PE and EVOH recovered — and are exactly the
scale factors the workbook itself uses.)

**`rho_S` is now derived, not assumed:**
```
rho_S = 1 - 0.97*(0.60 + 0.10) = 0.321      (brief guessed ~0.32)
```

**Gasification CAPEX follows a clean six-tenths rule.** The authors hard-code four
capacities; fitting `CAPEX = A·F^n` to two of them gives **n = 0.6000, A = 15,749.6**
and reproduces the other two to <0.1%:

| F (t/yr) | authors' USD/yr | fit | error |
|---|---|---|---|
| 2,400 | 1,680,303 | 1,679,096 | 0.07% |
| 3,200 | 1,996,874 | *(fit point)* | — |
| 7,200 | 3,248,331 | *(fit point)* | — |
| 8,000 | 3,460,308 | 3,459,341 | 0.03% |

Note their column is headed **"CAPEX \[USD/yr\]"** — already annualized, so `CRF` is
not applied on top for agent G.

---

## 3. The emissions "1000×" discrepancy — **resolved**

The brief was right to flag it, and the cause is a **label error, not a data error**.

Every factor in `[XLSX]` sits in a column headed `GWP [tonCO2e/ton resin]`, with
landfill = 0.0816. Then:

```
0.0816 tCO2e/ton × 8,000 ton/yr = 652.80      ← exactly Table 8's "652.80"
```

So the data is in **tonnes**, and Table 8/9/10's header *"Emissions \[kg CO₂-eq/year\]"*
should read **t CO₂-eq/yr**. Corroboration: Table 6 gives the bound
`U_g = 21,303.36 **tonCO2eq**` — same order as the table entries. And the max-profit
pathway then works out to **1.94 tCO₂e per tonne of plastic**, squarely in the
normal LCA range (~2–3 t/t for incineration).

**`EMIS_UNIT_SCALE = 1.0`. No 1000× correction is applied anywhere.** If you need the
paper's printed table verbatim, fix the *label*.

---

## 4. Still genuinely assumed — results rest on these

| Parameter | Value | Why |
|---|---|---|
| `P_RAW` | 0 USD/ton | Paper gives the planner feedstock free. **But** its own model values this waste at **110 USD/ton** (`[JULIA]` cell 47 `Cgas_pw`) — recorded as `PAPER_WASTE_TRANSFER_PRICE`, not swept in v1. |
| `C_LF` | 60 USD/ton | Brief's default. Paper's own value is **7.836** — ~8× below any real US gate rate. |
| `CRF` | 0.1175 | Brief's default. Paper annualizes by **÷20, undiscounted** (`CRF = 0.05`). |
| `OPEX_W_PER_TON` | 75 USD/ton | **Real gap.** Paper records incineration OPEX = 0 and CAPEX = 0 — it models incineration as a third-party *off-take market* (sells waste at 110 USD/t), never an owned facility. 75 USD/t is mid-range US WTE O&M. |
| `CAPEX_W` | 30 M USD | Same gap. Viability only; never affects `q*`. |
| `RHO_W` / `RHO_G` | 0.15 / 0.08 | Paper records both as **0.0 t/t**, which isn't physical. Used the brief's values. |
| `CAP_S/W/G` | 6,000 / 4,000 / 4,000 | Brief's defaults; total 14,000 > 8,000 so the shared constraint binds. |
| `OPEX_CURVATURE_RATIO` | 1.20 | Brief's rule. For ratio = 1.2 it collapses to **`b_i = a_i / Cap_i`** exactly. |

---

## 5. Resulting agent parameters and the implied base case

```
       Cap     revenue      a_i        b_i         m_i    rho    e_i        ACC
    ton/yr       USD/t    USD/t    USD/t^2       USD/t    t/t tCO2/t     USD/yr
 S   6,000    1,468.39   186.77   0.031128    1,262.36  0.321  1.221  6,303,320
 W   4,000      259.57    50.00   0.012500      200.57  0.150  2.393  3,525,000
 G   4,000      147.98   106.58   0.026645       36.60  0.080  1.077  2,282,998
```

Analytic 1-D bisection on `Σ q_i(λ) = Q_tot` (the same check that becomes test #1):

```
base-case lambda = 175.57 USD/ton
  q_S = 6,000  (75%)   CAPACITY-constrained
  q_W = 2,000  (25%)   margin sets the price -> W is the marginal agent
  q_G =     0  ( 0%)   priced out (m_G = 36.60 < lambda)
aggregate unconstrained demand = 11,373.7 t/yr  ->  lambda hits 0 there
```

**Expect a jump discontinuity in Figure 1 at Q_tot = 6,000.** Below 6,000 STRAP is
the marginal buyer and λ ≈ 1,076–1,262 USD/t; the instant STRAP caps out, incineration
becomes marginal and λ drops to ≈ 200 USD/t. λ stays monotone non-increasing (test #7
is safe), and the merit order **S → W → G** is exactly the story the brief wants.

Paper cross-check (test #10): routing all 8,000 t/yr to STRAP gives operating profit
**9.10 M USD/yr** vs Table 8's **7.55 M USD/yr** → **ratio 1.205**. Same order of
magnitude, as required.

---

## 6. Two things I could not reconcile — flagging, not fixing

**(a) Table 8's 7.55e6 is not reproducible from the workbook's own per-wash costs.**

| convention | profit (USD/yr) | emissions (tCO₂e/yr) |
|---|---|---|
| shredder charged to **both** washes (the literal formula) | 5,613,069.68 | 19,786.29 |
| shredder charged **once** | 6,838,566 | 19,353.70 |
| wash-1 + shredder CAPEX only, all three OPEX lines | **7,566,449** *(0.2% off)* | — |
| **paper, Table 8** | **7,551,142** | **15,548.59** |

The first row's two numbers appear **verbatim** in `[XLSX] 'Final Results December'`
cells **B28 and B29**, so that is the authors' own full-accounting figure. The
published 7.55e6 appears to omit the wash-2 capital charge. I do **not** try to
reproduce their pathway bookkeeping — `data.py` uses the unambiguous per-unit
BioSTEAM data and counts the shredder once.

**(b) Agent G has a thin/negative margin at the paper's own data.**

```
REV_G                    = 147.98 USD/ton
avg OPEX at nameplate    = 159.87 USD/ton
                           ---------------
avg margin               = -11.89 USD/ton   (before residue disposal and feedstock)
```

Consistent with the paper: gasification-for-energy-recovery is **never selected in
any reported optimal solution** (Tables 8–12 always pick gas-to-H₂, incineration, or
landfill).

Because the OPEX curve is convex, G's *marginal* cost at low throughput sits below
its *average* cost at nameplate, so `m_G = +36.60` and **G does enter once feedstock
is abundant (Q_tot > 10,000 t/yr), operating at ~1,374 t/yr — well below nameplate.**
That's an economically meaningful outcome, and it's what gives Figure 2 its third tier.

Two inputs behind `REV_G` look dimensionally suspect and are flagged, not corrected:
- `price_heat = 0.13 USD/MJ` (= 130 USD/GJ; industrial heat is 5–15 USD/GJ)
- `products_heat = 583.33 MJ/tonne` (plastics carry 30–40 GJ/tonne)

Correcting either makes G **less** viable, so the conclusion is robust.
`G_REVENUE_MULTIPLIER` is exposed (default 1.0) but **not swept in v1**.

---

## 7. Status

The model is built and verified — see [`Code/README.md`](Code/README.md) for how
to run it and [`ASSUMPTIONS_FOR_PAOLA.md`](ASSUMPTIONS_FOR_PAOLA.md) for the
questions these notes raise.

Three decisions taken here, all reversible in one line of `Code/data.py`:

1. **`REV_W = 259.57`** (`Cwte`, the energy product value) rather than `110`
   (`Cgas_pw`, the waste transfer price the paper's solved model actually uses),
   because our agent *operates* the incinerator. See Q2 in the assumptions file.
2. **`P_RAW = 0`** per the brief, even though the paper's own transfer price is
   110 USD/t. `PAPER_WASTE_TRANSFER_PRICE` is defined and ready to sweep.
3. **`C_LF = 60` and `CRF = 0.1175`** per the brief, overriding the paper's
   7.836 and 0.05. Both paper values are kept as cross-check constants.
