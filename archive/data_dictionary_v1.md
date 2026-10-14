# Data Dictionary v2 — EcoPackAI

Final schema documentation covering the materials dataset across all
three pipeline stages: cleaned, engineered, and model-ready.

## Dataset-Level Summary

| File | Rows | Columns | Format | Size |
|---|---|---|---|---|
| `data/final/materials_cleaned.parquet` | 403 | 23 | Parquet | ~32 KB (vs ~100 KB as CSV) |
| `data/final/materials_engineered.parquet` | 403 | 42 | Parquet | ~60 KB (vs ~196 KB as CSV) |
| `data/final/materials_model_ready.parquet` | 403 | 34 | Parquet | ~44 KB (vs ~144 KB as CSV) |

Parquet files are roughly 3x smaller than their CSV equivalents and
preserve column data types natively, avoiding re-parsing errors that
CSVs can introduce (e.g. numbers being misread as text).

### Feature Groups

- **Raw / cleaned (23 cols):** original material attributes after
  ingestion cleaning (snake_case columns, no missing values).
- **Encoded / scaled (34 cols):** one-hot encoded categorical columns
  + MinMax-scaled numeric columns, ready for direct use as ML features.
- **Engineered (42 cols):** encoded columns plus the five intermediate
  scores and the three final indices (CII, CEI, MSS).

## Column-Level Details

### Identifiers

| Column | Type | Description | Nullable | Derived | Used in ML |
|---|---|---|---|---|---|
| `material_id` | string | Unique material identifier (e.g. MAT_0001) | No | No | No (key only) |

### Categorical (raw, pre-encoding)

| Column | Type | Description | Allowed Values | Nullable | Derived | Used in ML |
|---|---|---|---|---|---|---|
| `material_type` | string | Broad material category | Cardboard, Plastic, Paper/Bio-Based, Steel | No | No | Yes (one-hot) |
| `packaging_type` | string | Specific packaging form | 6 values, see `data_quality_rules.md` | No | No | Yes (one-hot) |
| `supplier_region` | string | Sourcing region | EMEA, APAC, AMERICAS, ROW, LATAM, EU | No | No | Yes (one-hot) |
| `recyclability_category` | string | Recyclability bucket | Low, Medium, High (only Medium/High present in current data) | No | No | Yes (ordinal-encoded) |

### Numeric (raw, pre-scaling)

| Column | Type | Range | Description | Used in ML |
|---|---|---|---|---|
| `cost_per_unit_usd` | float | 0.21-25.95 | Price per packaging unit | Yes (scaled) |
| `co2_emission_per_kg` | float | 0.28-3.25 | CO2 emitted per kg of material | Yes (scaled) |
| `biodegradation_time_days` | float | 31-180,208 | Days to naturally decompose | Yes (scaled) |
| `load_handling_score` | float | 1-10 | Load-bearing capability | Yes (scaled) |
| `moisture_resistance_score` | float | 1-10 | Resistance to moisture | Yes (scaled) |
| `thermal_resistance_score` | float | 1-10 | Resistance to temperature extremes | Yes (scaled) |
| (10 additional percent/weight columns) | float | see `data_quality_rules.md` | Various sustainability/supplier metrics | Yes (scaled) |

### Engineered Features

| Column | Type | Range | Description | Used in ML |
|---|---|---|---|---|
| `co2_impact_index` | float | 0-100 | Sustainability score (see `feature_engineering_document.md`) | Yes (target-adjacent) |
| `cost_efficiency_index` | float | 0-100 | Economic feasibility score | Yes (target-adjacent) |
| `material_suitability_score` | float | 0-100 | General robustness/suitability profile | Yes (target-adjacent) |

## Notes

- `data/final/` holds the production-ready Parquet copies. `data/processed/`
  and `data/model_ready/` retain the original CSVs for readability during
  development.
- The three engineered indices are documented in full mathematical
  detail in `docs/feature_engineering_document.md`.
- All ranges and categories in this document were verified against the
  real dataset, not assumed from the generic project brief.
