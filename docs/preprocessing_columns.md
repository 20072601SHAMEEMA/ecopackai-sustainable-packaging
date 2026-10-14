# Preprocessing Columns — ColumnTransformer Groups

Defines which columns from `materials.csv` (cleaned) go through which
transformer branch in `preprocessing_pipeline.pkl`.

## Numeric Columns (14) — Median Impute + StandardScaler

```
recyclability_percent, recycled_content_percent, reusability_percent,
biodegradation_time_days, end_of_life_disposal_percent,
carbon_footprint_kg_co2_per_unit, waste_reduction_impact_percent,
sustainability_target_progress_percent, load_handling_score,
moisture_resistance_score, thermal_resistance_score,
annual_usage_units, total_material_weight_tons,
supplier_sustainability_compliance_percent
```

## Nominal Categorical Columns (3) — Most-Frequent Impute + One-Hot Encode

```
material_type, packaging_type, supplier_region
```

## Ordinal Categorical Columns (1) — Most-Frequent Impute + Ordinal Encode

```
recyclability_category   (explicit order: Low < Medium < High)
```

## Excluded Columns (not passed to the pipeline)

```
material_id                        -- identifier
suitable_product_categories        -- free text
recommended_packaging_use_cases    -- free text
cost_per_unit_usd                  -- prediction target (Random Forest)
co2_emission_per_kg                -- prediction target (XGBoost)
```

`remainder='drop'` is set on the `ColumnTransformer`, so any column not
explicitly listed above (including the excluded ones) is automatically
dropped rather than silently passed through unprocessed.

## Output Shape

- Input: 18 usable columns (14 numeric + 3 nominal + 1 ordinal)
- Output after transformation: 31 columns (one-hot encoding expands
  `material_type`, `packaging_type`, and `supplier_region` into
  multiple binary columns each)
