# Feature Transformation Plan — EcoPackAI

Step-by-step description of how the three engineered features are
computed from `materials_final_encoded.csv`. See
`feature_engineering_document.md` for the underlying formulas and
reasoning.

## Step 1: Load the encoded materials dataset

Load `data/model_ready/materials_final_encoded.csv`, which already
contains scaled numeric columns and encoded categorical columns from
the preprocessing stage.

## Step 2: Compute component scores

For each material record:

1. Invert `co2_emission_per_kg_scaled` to get `co2_score` (lower
   emissions -> higher score).
2. Invert `biodegradation_time_days_scaled` to get `green_score`
   (faster biodegradation -> higher score).
3. Normalize `recyclability_category_encoded` (0/1/2) to a 0-1 range
   by dividing by 2, producing `recyclability_score`.
4. Average `load_handling_score_scaled`, `moisture_resistance_score_scaled`,
   and `thermal_resistance_score_scaled` to get `durability_score`.
5. Invert `cost_per_unit_usd_scaled` to get `cost_score`.

## Step 3: Combine into the three indices

1. **CO2 Impact Index** = weighted sum of `co2_score` (50%),
   `green_score` (30%), and `recyclability_score` (20%), scaled to 0-100.
2. **Cost Efficiency Index** = weighted sum of `cost_score` (50%),
   `durability_score` (30%), and `recyclability_score` (20%), scaled
   to 0-100.
3. **Material Suitability Score** = simple average of
   `load_handling_score_scaled`, `moisture_resistance_score_scaled`,
   and `thermal_resistance_score_scaled`, scaled to 0-100.

## Step 4: Attach to the dataset

Append `co2_impact_index`, `cost_efficiency_index`, and
`material_suitability_score` as new columns on the materials dataset,
keyed by `material_id`.

## Step 5: Validate

Confirm all three new columns fall within the expected 0-100 range,
and spot-check a few rows against their raw values (e.g. Steel should
score low on CII given its long biodegradation time and high CO2
emissions).

## Step 6: Export

Save the updated dataset to
`data/model_ready/materials_with_features.csv`.