# Data Quality Rules — EcoPackAI

Validation rules for `materials.csv`, `materials_final_encoded.csv`, and
`materials_with_features.csv`. Adapted to the actual categories present
in the real dataset (the original task brief assumed generic categories
such as Box/Pouch/Tray and A/B/C/D recyclability, which do not match
the data actually provided — see `data_validation_report.md`).

## Mandatory Columns (no nulls allowed)

`material_id`, `material_type`, `cost_per_unit_usd`, `co2_emission_per_kg`,
`recyclability_percent`, `biodegradation_time_days`.

## Allowed Value Ranges

| Column | Rule |
|---|---|
| `cost_per_unit_usd` | > 0 |
| `co2_emission_per_kg` | >= 0 |
| `moisture_resistance_score` | 1-10 |
| `thermal_resistance_score` | 1-10 |
| `load_handling_score` | 1-10 |
| `biodegradation_time_days` | >= 1 |
| `recyclability_percent`, `recycled_content_percent`, `reusability_percent`, `end_of_life_disposal_percent`, `waste_reduction_impact_percent`, `sustainability_target_progress_percent`, `supplier_sustainability_compliance_percent` | 0-100 |

## Allowed Categories (as found in the real dataset)

- **Material Type:** Cardboard, Plastic, Paper/Bio-Based, Steel
- **Packaging Type:** Cardboard Boxes, Protective Fillers (Paper/Biodegradable),
  Steel Racks & Containers, Foldable & Stackable Containers,
  Bubble Wrap (Minimal Use), Plastic Totes & Pallets
- **Recyclability Category:** Low, Medium, High
  (note: the current dataset contains only Medium and High — no material
  is rated Low)
- **Supplier Region:** EMEA, APAC, AMERICAS, ROW, LATAM, EU

## Uniqueness & Integrity Rules

- `material_id` must be unique (no duplicates)
- No fully duplicate rows
- No negative values in any weight, cost, or count column

## Feature Engineering Validation Rules

- `co2_impact_index`, `cost_efficiency_index`, `material_suitability_score`
  must all fall strictly within 0-100
- None of the three engineered scores may be NaN or infinite

## Columns Requiring Deduplication

`material_id` (primary key candidate for the materials table).

## Columns Needing Normalization

All numeric columns listed under "Numeric Scaling" in
`encoding_normalization_report.md` (scaled via `MinMaxScaler` to 0-1
before feature engineering).

## Columns to Assert Correctness On

`co2_impact_index`, `cost_efficiency_index`, `material_suitability_score`
(engineered outputs), `recyclability_category_encoded` (must only be
0, 1, or 2).