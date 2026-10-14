# Model Explainability — EcoPackAI

**Notebook:** `ml/notebooks/05_model_explainability.ipynb`
**Outputs:** `outputs/explainability/` — `shap_summary.png`, `feature_importance.png`,
`shap_local_cost_high.png`, `shap_local_cost_low.png`, `shap_local_co2_high.png`,
`shap_local_co2_low.png`, `shap_importance.csv`, `permutation_importance.csv`

## 1. What Was Explained and How

| Model | Target | Artifact |
|---|---|---|
| Random Forest | `cost_per_unit_usd` | `ml/models/rf_cost.joblib` |
| XGBoost | `co2_emission_per_kg` | `ml/models/xgb_co2.joblib` |

All explanations use the **81 held-out test materials** (never seen in training).

**SHAP (TreeExplainer)** splits every single prediction into a base value (the average
prediction) plus one contribution per feature. Check: base value + contributions equals
the model's prediction for all 81 materials (max gap 1e-13 for cost, 1e-6 for CO2).
- *Global:* mean |SHAP| per feature. For one-hot encoded columns (material_type,
  packaging_type, supplier_region) the contributions are summed back to the original
  column, so the ranking covers the 18 raw input features.
- *Local:* waterfall plots for the highest and lowest prediction of each model.

**Permutation importance** (model-agnostic) shuffles one raw input column at a time
(30 repeats) and measures how much the test RMSE gets worse. It runs on the full
pipeline, so it ranks the same 18 raw features a user supplies.

## 2. Global Results

### Cost model (Random Forest)

| Rank | Feature | Share of SHAP impact | Permutation: RMSE increase ($) |
|---|---|---|---|
| 1 | reusability_percent | 48.4% | 5.24 |
| 2 | waste_reduction_impact_percent | 27.5% | 2.87 |
| 3 | total_material_weight_tons | 9.0% | 1.82 |
| 4 | recycled_content_percent | 3.0% | 0.34 |
| 5 | material_type | 2.9% | 0.30 |
| 6 | packaging_type | 2.5% | 0.28 |

### CO2 model (XGBoost)

| Rank | Feature | Share of SHAP impact | Permutation: RMSE increase (kg/kg) |
|---|---|---|---|
| 1 | biodegradation_time_days | 30.9% | 0.314 |
| 2 | end_of_life_disposal_percent | 22.1% | 0.238 |
| 3 | recycled_content_percent | 12.0% | 0.215 |
| 4 | load_handling_score | 8.2% | 0.062 |
| 5 | annual_usage_units | 6.9% | 0.069 |
| 6 | carbon_footprint_kg_co2_per_unit | 4.6% | 0.063 |

**Both methods agree.** The top 3 features are identical and in the same order for both
models; ranks 4–8 differ by at most a few places.

## 3. Interpretation and Domain Check

**Cost is driven by how durable and reusable the packaging is.** Median values by
packaging type:

| Packaging type | Reusability % | Waste reduction % | Median cost ($) |
|---|---|---|---|
| Bubble Wrap | 12 | 32 | 1.4 |
| Protective Fillers (paper) | 31 | 66 | 2.0 |
| Cardboard Boxes | 50 | 60 | 3.0 |
| Foldable & Stackable Containers | 89 | 75 | 12.0 |
| Plastic Totes & Pallets | 96 | 80 | 14.7 |
| Steel Racks & Containers | 98 | 84 | 25.0 |

Single-use packaging is cheap per unit; durable, reusable containers cost more up front.
This matches industry reality (reusable totes and steel racks are capital items).
Spearman correlation of reusability with cost: 0.91.

**CO2 is driven by what the material is made of and how it ends its life.** Slow
biodegradation (plastics and steel: tens of thousands of days; paper and cardboard:
~130–200 days) and a higher share of end-of-life disposal go with higher CO2 per kg
(Spearman 0.82 and 0.73). Paper-based materials degrade fast and score lowest. This
matches life-cycle knowledge: fossil-based plastics and steel are more carbon-intensive
per kg than paper and cardboard.

**Material type is learned through its properties.** `material_type` itself ranks only
5th (cost) and outside the top 8 (CO2), because properties such as reusability and
biodegradation time separate the material groups just as cleanly. The models effectively
identify the material group from its properties, consistent with the earlier finding
that CO2 is set by material type.

## 4. Local Explanations (sample predictions)

| Plot | Material | Prediction | Main reasons (SHAP, from base value) |
|---|---|---|---|
| `shap_local_cost_high.png` | MAT_0230, Steel Racks & Containers | $25.52 (actual $25.68) | base $8.99; reusability 97% +5.41, weight 5,063 t +4.60, waste reduction 83% +3.18 |
| `shap_local_cost_low.png` | MAT_0071, Bubble Wrap | $1.23 (actual $1.47) | reusability 9% −4.10, waste reduction 32% −2.16, weight 267 t −0.75 |
| `shap_local_co2_high.png` | MAT_0230, Steel Racks & Containers | 3.06 (actual 3.02) | base 1.17; recycled content 71% +0.34, biodegradation 99,557 days +0.34, carbon footprint per unit +0.28 |
| `shap_local_co2_low.png` | MAT_0010, Protective Fillers (paper) | 0.31 (actual 0.29) | biodegradation 31 days −0.33, end-of-life disposal 3% −0.25 |

**One counter-intuitive attribution.** For the steel container, recycled content (71%)
*raises* the CO2 prediction, although across the catalogue recycled content goes with
*lower* CO2 (Spearman −0.72). Several features move together because each acts as a
proxy for material type, so SHAP can share credit among them in ways that look odd for
one feature in isolation. The prediction itself is accurate (3.06 vs 3.02); the lesson is
to read correlated features as a group, not one by one.

## 5. Validation Checklist

| Check | Result |
|---|---|
| Key features logically influence predictions | Yes: reusability/durability drive cost; biodegradability/end-of-life drive CO2 (section 3) |
| No leakage-related features dominate | No target or target-derived column is an input (asserted in the notebook). The most CO2-like input, `carbon_footprint_kg_co2_per_unit`, has 4.6% of the CO2 model's impact (rank 6). The largest single share is 48% (reusability, cost model), a genuine material property |
| Explanations align with domain knowledge | Yes, with one documented counter-intuitive local attribution (section 4) |
| Plots reproducible and interpretable | Two full runs give byte-identical PNG and CSV files (SHAP's random dot jitter is seeded; CSVs rounded to 6 decimals). Plots use readable feature names and real units |

## 6. Limitations

- 403 materials in 6 packaging groups; features are strongly correlated within groups,
  so importance is shared among proxies and individual rankings beyond the top 3 are not
  very stable.
- Explanations describe what the model learned from this dataset, not causal effects:
  making a material more reusable would not by itself make it more expensive.
- One test material (MAT_0010, biodegradation 31 days) lies below the training range
  (44 days); its explanation is still sensible, and the predictor warns about such inputs.
