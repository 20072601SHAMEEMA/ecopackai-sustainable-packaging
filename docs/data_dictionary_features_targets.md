# Features & Targets — Dataset Preparation

## Target Variables

Two regression targets were selected, both real-world numeric values
(not scaled), matching the original project architecture (Random
Forest for cost, XGBoost for CO2):

| Target | Column | Type | Description |
|---|---|---|---|
| Cost prediction | `cost_per_unit_usd` | Regression | Real cost in USD per packaging unit, used to train the Random Forest model |
| CO2 prediction | `co2_emission_per_kg` | Regression | Real CO2 emission per kg of material, used to train the XGBoost model |

**Note on scope:** an earlier draft of this task (based on a generic
team template) proposed a `recommended_material` classification target.
This was reviewed and intentionally not used: on inspection, that
target would need to be derived from `material_type` itself, which
would also appear as an input feature — this is data leakage (the
model would just learn to copy its own input, not make a genuine
prediction). The two regression targets above are grounded in real,
independent columns and match the system's original architecture
document.

## Final Feature List (32 features)

Feature groups included:

- **Material identity (one-hot encoded):** `material_type_*`,
  `packaging_type_*`, `supplier_region_*`
- **Recyclability:** `recyclability_category_encoded`
- **Physical properties (scaled):** `load_handling_score_scaled`,
  `moisture_resistance_score_scaled`, `thermal_resistance_score_scaled`
- **Sustainability metrics (scaled):** `recyclability_percent_scaled`,
  `recycled_content_percent_scaled`, `reusability_percent_scaled`,
  `end_of_life_disposal_percent_scaled`,
  `waste_reduction_impact_percent_scaled`,
  `sustainability_target_progress_percent_scaled`,
  `supplier_sustainability_compliance_percent_scaled`
- **Operational metrics (scaled):** `annual_usage_units_scaled`,
  `total_material_weight_tons_scaled`
- **Engineered feature:** `material_suitability_score` (safe to include
  — built only from load/moisture/thermal scores, unrelated to either
  target)

## Columns Excluded from Features (Leakage Prevention)

| Column | Reason for Exclusion |
|---|---|
| `material_id` | Identifier, not a predictive feature |
| `cost_per_unit_usd`, `co2_emission_per_kg` | The raw target columns themselves |
| `cost_per_unit_usd_scaled`, `co2_emission_per_kg_scaled` | Scaled versions of the targets — same information |
| `co2_impact_index`, `cost_efficiency_index` | Engineered directly from the target columns |
| `co2_score`, `green_score`, `recyclability_score`, `durability_score`, `cost_score` | Intermediate scores used to build the indices above, also derived from the targets |
| `biodegradation_time_days_scaled` | Used in computing `co2_impact_index`; kept out for consistency with the leakage exclusions above, since it fed directly into the CO2-related engineered score |

## Train/Test Split

- Split ratio: 80/20
- `random_state=42` used for both cost and CO2 splits to guarantee the
  same rows appear in each model's train/test sets, so results are
  directly comparable.
- Training set: 322 materials
- Test set: 81 materials

## Output Files

| File | Description |
|---|---|
| `data/model_input/X_raw.csv` | Full feature set, unsplit (403 rows) |
| `data/model_input/y_cost_raw.csv` | Full cost target, unsplit |
| `data/model_input/y_co2_raw.csv` | Full CO2 target, unsplit |
| `data/model_input/X_train.csv`, `X_test.csv` | Split feature sets |
| `data/model_input/y_cost_train.csv`, `y_cost_test.csv` | Split cost targets |
| `data/model_input/y_co2_train.csv`, `y_co2_test.csv` | Split CO2 targets |
