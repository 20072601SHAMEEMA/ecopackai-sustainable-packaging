# Feature Engineering Document — EcoPackAI

Defines the mathematical formulas and assumptions behind the three
engineered features: CO2 Impact Index (CII), Cost Efficiency Index
(CEI), and Material Suitability Score (MSS).

**Note on data schema:** the original task brief assumed a recyclability
scale of A-D. The real dataset instead uses Low/Medium/High, already
encoded numerically as `recyclability_category_encoded` (Low=0,
Medium=1, High=2) during preprocessing (see `encoding_normalization_report.md`).
All formulas below use the columns that actually exist in
`materials_final_encoded.csv`.

## 1. CO2 Impact Index (CII)

**Goal:** standardize the environmental impact of a material using its
CO2 emissions, biodegradation time, and recyclability.

**Inputs used:**
- `co2_emission_per_kg_scaled` (already 0-1 from MinMaxScaler)
- `biodegradation_time_days_scaled` (already 0-1 from MinMaxScaler)
- `recyclability_category_encoded` (0, 1, or 2)

**Logic:**
1. Lower CO2 emission is better, so the score is inverted:
   `co2_score = 1 - co2_emission_per_kg_scaled`
2. Faster biodegradation is better (greener), so this is also inverted:
   `green_score = 1 - biodegradation_time_days_scaled`
3. Recyclability is normalized to a 0-1 scale:
   `recyclability_score = recyclability_category_encoded / 2`
4. The three components are combined with weights reflecting their
   relative importance to sustainability (CO2 weighted highest, since
   it is the most direct environmental cost):

```
CII = (0.5 * co2_score + 0.3 * green_score + 0.2 * recyclability_score) * 100
```

**Output range:** 0-100 (higher = more sustainable).

**Assumption:** weights (0.5 / 0.3 / 0.2) are a reasonable starting
point based on CO2 being the most commonly cited environmental metric
in packaging sustainability guidelines. These are adjustable if the
project needs different priorities.

## 2. Cost Efficiency Index (CEI)

**Goal:** capture the economic feasibility of using a material,
factoring in not just raw price but durability and reuse potential.

**Inputs used:**
- `cost_per_unit_usd_scaled`
- `load_handling_score_scaled`, `moisture_resistance_score_scaled`,
  `thermal_resistance_score_scaled` (used together as a durability proxy)
- `recyclability_category_encoded`

**Logic:**
1. Lower cost is better, so inverted:
   `cost_score = 1 - cost_per_unit_usd_scaled`
2. Durability proxy is the average of the three resistance/handling
   scores, since the dataset has no single "durability" column:
   `durability_score = mean(load_handling_score_scaled, moisture_resistance_score_scaled, thermal_resistance_score_scaled)`
3. Recyclable/reusable materials reduce long-term cost (fewer
   replacements, disposal savings), so this is included as a bonus:
   `recyclability_bonus = recyclability_category_encoded / 2`
4. Combined:

```
CEI = (0.5 * cost_score + 0.3 * durability_score + 0.2 * recyclability_bonus) * 100
```

**Output range:** 0-100 (higher = more cost-efficient).

**Assumption:** durability is approximated from the three resistance
scores, since no direct "durability rating" column exists in the raw
data. This is a reasonable proxy but could be refined if a true
durability metric becomes available.

## 3. Material Suitability Score (MSS)

**Goal:** describe how robust/appropriate a material is across
handling conditions.

**Scope decision:** the original brief describes MSS as matching a
material against a *specific product's* requirements (e.g. penalizing
a material if it fails a product's heat-sensitivity requirement). That
requires a material-to-product match at recommendation time, not a
static score computed once per material. For this stage, MSS is
computed as a **general robustness profile per material** — how well
it performs across load, moisture, and thermal conditions in general.
The per-product matching logic (comparing a material's MSS against a
specific product's `fragility_index` and `shipping_type`) belongs to
the recommendation engine (Module 4), where a material and a product
are considered together.

**Inputs used:**
- `load_handling_score_scaled`
- `moisture_resistance_score_scaled`
- `thermal_resistance_score_scaled`

**Logic:**
```
MSS = mean(load_handling_score_scaled, moisture_resistance_score_scaled, thermal_resistance_score_scaled) * 100
```

**Output range:** 0-100 (higher = more generally robust/suitable).

**Assumption:** equal weighting across the three resistance dimensions,
since the brief does not specify a priority order between load,
moisture, and thermal handling. This can be revisited once specific
product categories are matched against materials in Module 4.

## Combined Output

Each material record in the engineered dataset will include three new
columns: `co2_impact_index`, `cost_efficiency_index`, and
`material_suitability_score`, each ranging 0-100.

A **Final Recommendation Score** (weighted average of the three) is
deferred to Module 4, once the recommendation engine defines how much
weight sustainability, cost, and suitability should each carry for a
given product's priorities.