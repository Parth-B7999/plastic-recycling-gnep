# Questions for Paola — parameters I had to assume

**Context.** I'm extending the multilayer-film paper to a multi-agent
(Generalized Nash) setting: STRAP, incineration and gasification become three
independent firms competing for one shared 8 kt/yr feedstock pool. The output is
the shadow price **λ** (USD/ton) on that shared pool.

Most parameters came straight out of the paper, the Julia notebook
(`PIW Paper Dec 21 w Transportation.ipynb`) or the workbook
(`Data for model_Scenarios.xlsx`). The items below did **not**, and every result
that moves with them is provisional. Each has a concrete question.

Everything is coded in `Code/data.py`, tagged `# ASSUMED` with the same
reasoning, and printed loudly at the end of every run.

---

## A. The three that most change the answer

### 1. Incineration operating cost — `OPEX_W_PER_TON = 75 USD/ton`

**The gap.** The workbook (`Othertech!O3`) records incineration **OPEX = 0 and
CAPEX = 0**, because the paper models incineration as a *third-party off-take
market* — the planner **sells** waste to it at 110 USD/ton — never as a facility
anyone owns and runs. In my setting incineration has to be a firm that operates
a plant, so it needs an operating cost.

**What I used.** 75 USD/ton, mid-range US MSW waste-to-energy O&M (typical
60–90 USD/ton).

> **Q1: Do you have a per-ton O&M figure for incineration on this feedstock, or
> a reference you'd trust? Anything in the 60–90 range, or is that wrong for
> Wisconsin?**

### 2. Incineration revenue — `REV_W = 259.57 USD/ton` (`Cwte`)

**The ambiguity.** The notebook defines two numbers that could both be
"incineration revenue":

| constant | value | what it is |
|---|---|---|
| `Cwte` (cell 24) | **259.57 USD/ton** | listed under "Cost of the products" beside `Cpe` and `Cevoh` — the value of the **energy sold** |
| `Cgas_pw` (cell 47) | **110 USD/ton** | the price the planner gets for **selling the waste** to incineration / gas-to-H₂ |

The solved model in cell 48 uses **110**, not `Cwte`. `Cwte` only appears in an
alternative Sales expression at cell 66.

**What I used.** 259.57, because my agent *operates* the incinerator and earns
the product value; 110 is what it would *pay* for feedstock.

> **Q2: Is `Cwte = 259.57 USD/ton` the value of the energy product per tonne
> burned? And is `Cgas_pw = 110` the gate/transfer price for the waste itself?
> If I have those backwards, incineration's margin changes by a factor of ~4.**

### 3. Capacities — `Cap_S / Cap_W / Cap_G = 6,000 / 4,000 / 4,000 t/yr`

**The gap.** The paper has no per-firm capacities (single planner, 8 kt/yr feed;
location Scenario 3 mentions a shared STRAP facility at 20 kt/yr).

**What I used.** Values summing to 14,000 > 8,000 so the shared constraint binds
and λ > 0 at base case.

**Why it matters most.** These drive the whole figure. With `Cap_S = 6,000`,
STRAP saturates at exactly Q_tot = 6,000 and λ **jumps** from ~1,076 down to
~201 USD/ton. Move `Cap_S` and that cliff moves with it.

> **Q3: Is there a defensible single-plant scale for STRAP? Would ~6 kt/yr be
> reasonable for one firm, given the 20 kt/yr shared-facility figure? And is
> there any basis for incineration / gasification capacities, or should I sweep
> them instead of fixing them?**

---

## B. Three where the paper has a number but I deliberately used a different one

I followed the brief here, but the paper's own values differ a lot. Both are in
`data.py` so switching is one line.

| parameter | I used | the paper's own value | source of the paper's value |
|---|---|---|---|
| landfill tipping fee `C_LF` | **60 USD/ton** | **7.836 USD/ton** | `Othertech!O2`; confirms Table 8's −6.27e4 exactly (8,000 × 7.836) |
| capital recovery factor `CRF` | **0.1175** (10%, 20 yr, discounted) | **0.05** (÷20, undiscounted) | `StrapScenario1 Units!P` = `StrapScenario1!P/20` |
| feedstock price `p_raw` | **0 USD/ton** | **110 USD/ton** implied | `Cgas_pw`, the waste transfer price |

> **Q4: Is 7.836 USD/ton really the landfill gate fee? Real Wisconsin MSW rates
> are ~45–60 USD/ton, so 7.836 looks about 8× low — is it a per-ton *processing*
> cost rather than a tipping fee, or a unit slip?**

> **Q5: Was the ÷20 straight-line annualization deliberate (i.e. undiscounted),
> or should CAPEX be annualized with a real capital recovery factor?**

> **Q6: For a multi-agent setting, what's the right feedstock price? The paper
> gives the planner its waste free. Post-industrial waste often carries a
> *negative* price (the generator pays to offload it). Is 110 USD/ton the number
> a recycler would actually pay, or is it more like −50?**

---

## C. Smaller assumptions (unlikely to change conclusions)

| parameter | I used | note |
|---|---|---|
| `RHO_W` incineration ash | 0.15 t/t | workbook records **0.0**, which isn't physical (bottom+fly ash is 10–20%) |
| `RHO_G` gasification ash/char | 0.08 t/t | workbook also records **0.0** |
| `CAPEX_W` incineration capital | 30 M USD @ 4 kt/yr | not in the paper; affects viability only, never the equilibrium `q*` |
| `OPEX_CURVATURE_RATIO` | 1.20 | per-ton OPEX at full capacity ÷ per-ton at half. Makes each firm's problem strictly concave, which is what guarantees a unique equilibrium and a smooth λ |

> **Q7: Are the zero "Waste to Disposal" entries for incineration and
> gasification intentional (e.g. ash counted elsewhere), or placeholders?**

---

## D. Two things I found that may be worth flagging regardless

### The emissions unit discrepancy resolves as a **label error**

Table 8 reads *"Emissions [kg CO₂-eq/year]"*, but the underlying data is in
**tonnes**:

```
0.0816 tCO2e/ton × 8,000 ton/yr = 652.80      ← exactly Table 8's landfill figure
```

Table 6 also gives the bound as `U_g = 21,303.36 **tonCO2eq**`, same order as the
table entries, and the max-profit pathway then works out to **1.94 tCO₂e per
tonne of plastic** — normal LCA range. So the numbers are right and the column
*header* should read **t CO₂-eq/yr**.

> **Q8: Can you confirm the Table 8/9/10 emissions columns are tonnes, not kg?**

### Table 8's 7.55e6 doesn't rebuild from the workbook's per-wash costs

| accounting convention | profit (USD/yr) | emissions (tCO₂e/yr) |
|---|---|---|
| shredder charged to **both** washes (the literal formula) | 5,613,069.68 | 19,786.29 |
| shredder charged **once** | 6,838,566 | 19,353.70 |
| wash-1 + shredder CAPEX only, all three OPEX lines | **7,566,449** (0.2% off) | — |
| **published, Table 8** | **7,551,142** | **15,548.59** |

The first row's two numbers appear **verbatim** in `Final Results December!B28`
and `!B29`, so that's the workbook's own full-accounting figure. The published
number looks like it omits the wash-2 capital charge.

> **Q9: Which CAPEX convention produced the published Table 8 numbers — is the
> shredder meant to be charged once or per wash, and is the wash-2 capital
> included?**

### Gasification-for-energy-recovery loses money at nameplate

```
revenue  Cgas_er        = 147.98 USD/ton   (notebook cell 47)
OPEX at nameplate       = 159.87 USD/ton   (Gasification_Technologies!X2)
                          --------------
                          -11.89 USD/ton
```

This is consistent with the paper — gas-for-energy-recovery is never selected in
any reported optimum. But two inputs behind that revenue look dimensionally odd:

- `price_heat = 0.13 USD/MJ` (= 130 USD/GJ; industrial heat is 5–15 USD/GJ)
- `products_heat = 583.33 MJ/tonne` (plastics carry 30–40 GJ/tonne)

Correcting either makes it *less* viable, so the conclusion holds either way.

> **Q10: Are `price_heat` and `products_heat` in the units the notebook implies?
> 0.13 USD/MJ looks ~10× high and 583 MJ/tonne looks ~50× low.**

---

## What the answers would change

| if this changes | what moves |
|---|---|
| Q1, Q2 (incineration economics) | incineration's margin `m_W = 200.57`, which **sets λ at the base case**. λ = 175.57 today. |
| Q3 (capacities) | the location of the λ cliff and the whole merit order in Figure 2 |
| Q4, Q6 (landfill fee, feedstock price) | all three margins shift, but roughly in parallel — merit order likely survives |
| Q5 (CRF) | who is *viable* after CAPEX; **not** the equilibrium allocation or λ |
| Q7–Q10 | reporting and emissions only; no effect on λ or `q*` |
