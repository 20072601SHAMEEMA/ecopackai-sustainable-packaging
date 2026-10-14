# Data Quality Report — EcoPackAI

Based on exploratory analysis of `materials.csv` (403 rows, cleaned) and
`products.csv` (1500 rows, cleaned) in `data/processed/`.

## Missing Values

| Dataset | Rows Before | Rows With Missing Values | Action |
|---|---|---|---|
| materials.csv (raw) | 404 | 1 (MAT_0404, 14/23 columns) | Dropped |
| products.csv (raw) | 1500 | 0 | None needed |

See `missing_value_table.csv` for the per-column breakdown.

## Duplicates

No duplicate `material_id` values found in materials.csv.
No duplicate `product_id` values found in products.csv.

## Outliers

- **biodegradation_time_days**: ranges from 31 to 180,208 days. Fully
  explained by `material_type` — Cardboard (~90-355 days) and Paper/Bio-Based
  (~31-179 days) are low; Plastic (~10,935-98,971 days) and Steel
  (~63,481-180,208 days) are high. This reflects real material properties,
  not a data error, so no rows were removed. A log transform is recommended
  before this column is used as a model feature.
- **cost_per_unit_usd**: right-skewed distribution (most materials $0.21-$14.65,
  but Steel pushes the max to $25.95).

## Invalid Range Checks

All percentage-based columns (`recyclability_percent`, `recycled_content_percent`,
`reusability_percent`, `end_of_life_disposal_percent`,
`waste_reduction_impact_percent`, `sustainability_target_progress_percent`,
`supplier_sustainability_compliance_percent`) were checked for values outside
0-100. None found. `cost_per_unit_usd` and `product_weight_kg` were checked
for negative or zero values. None found. `fragility_index` confirmed to only
contain values 1-5.

## Data Quality Issues Found and Fixed

1. **Inconsistent category values** in products.csv: `"Cosmetics"` and
   `" Cosmetics"` (leading whitespace) were being treated as separate
   categories. Fixed by stripping whitespace.
2. **Inconsistent column naming** in materials.csv: raw headers used mixed
   case, spaces, and embedded units/symbols (e.g. `Cost per Unit (USD)`,
   `Recyclability (%)`). Standardized to snake_case to match the database
   schema.
3. **Class imbalance** in `material_type`: Plastic (199), Cardboard (139),
   Paper/Bio-Based (37), Steel (29). Underrepresented classes (Steel,
   Paper/Bio-Based) may produce less reliable model predictions.

## Correlation Notes

Several numeric features are strongly correlated with each other
(e.g. `moisture_resistance_score` and `thermal_resistance_score` at 0.89,
`co2_emission_per_kg` with several other features above 0.85). This
multicollinearity is not a concern for tree-based models (Random Forest,
XGBoost) but would need addressing if a linear model were used instead.

## Suggested Cleaning / Feature Engineering Approach for Next Stage

- Apply `log1p()` transform to `biodegradation_time_days` before modeling.
- One-hot or ordinal encode `material_type`, `supplier_region`,
  `recyclability_category`, `category` (products), and `shipping_type`.
- Consider a stratified train/test split on `material_type` to avoid the
  minority classes (Steel, Paper/Bio-Based) being underrepresented in
  either split.
- Build the CO2 Impact Index and Cost Efficiency Index features specified
  in the project brief using the existing CO2 and cost columns.
  