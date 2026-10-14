# Baseline Evaluation Report — EcoPackAI

## Summary of Results

| Model | Target | CV Mean MAE | CV Mean RMSE | CV Mean R2 | Test MAE | Test RMSE | Test R2 |
|---|---|---|---|---|---|---|---|
| Linear Regression | cost_per_unit_usd | 0.357 | 0.442 | 0.996 | 0.333 | 0.404 | 0.997 |
| Decision Tree | co2_emission_per_kg | 0.055 | 0.082 | 0.986 | 0.051 | 0.078 | 0.987 |

Cross-validation and test-set results are closely aligned for both
models (within 0.001-0.003 on R2), indicating the strong performance
is stable across different data splits, not a lucky one-off result.

## Why Performance Is Unusually High for a Baseline

Both baselines scored far higher (R2 > 0.98) than a typical first-pass
baseline would be expected to. Investigation traced this to the
dataset's structure rather than any modeling error:

1. **Cost is tightly clustered by material type.** Grouping
   `cost_per_unit_usd` by `material_type` shows narrow, largely
   non-overlapping ranges: Paper/Bio-Based ($1.23-$2.74), Cardboard
   ($2.24-$3.87), Plastic ($0.21-$15.76, wider spread), Steel
   ($24.22-$25.95). A model that correctly identifies material type
   can predict cost with very little additional information.

2. **`material_type` and `packaging_type` are perfectly correlated.**
   Every material type in this dataset maps to exactly one packaging
   type (e.g. all Steel materials use "Steel Racks & Containers").
   Inspecting the fitted Linear Regression coefficients confirmed
   this: `material_type_Steel` and `packaging_type_Steel Racks &
   Containers` had an identical coefficient (5.694), as did the
   Cardboard and Paper/Bio-Based pairs. This means the one-hot
   encoding for these two columns carries duplicate information, which
   inflates the apparent signal available to the model without adding
   genuinely new predictive power.

## Strengths and Weaknesses

**Linear Regression (cost):**
- Strength: highly interpretable — coefficients directly show that
  Steel drives cost up substantially, while Cardboard and Paper drive
  it down, matching the real-world intuition that metal packaging
  costs more than paper-based packaging.
- Weakness: the Plastic category has the widest cost range (0.21 to
  15.76), suggesting Plastic materials vary more by sub-type or
  quality grade than the current features fully capture. This is
  likely the largest source of remaining error.
- Weakness: multicollinearity between `material_type` and
  `packaging_type` means the model's coefficients are not as cleanly
  interpretable as they appear, since the two features are not
  independent.

**Decision Tree Regressor (CO2):**
- Strength: no linearity assumption needed, and still achieves strong
  performance, suggesting `co2_emission_per_kg` also follows
  material-type-driven thresholds rather than smooth linear trends.
- Weakness: unconstrained tree depth risks overfitting on a dataset
  this size (403 rows); the close match between CV and test scores
  suggests this has not yet become a problem, but should be monitored
  if the dataset grows or changes.

## Error Trends Across Material Types

The Plastic category is the most likely source of residual error for
cost prediction, given its unusually wide cost range compared to the
other three material types. This is worth a closer look in the next
modeling iteration — for example, checking whether an additional
feature (such as a plastic sub-grade, if available) would explain the
spread currently attributed to noise.

## Recommendation

These baselines set a strong reference point. Given the
multicollinearity identified between `material_type` and
`packaging_type`, it is worth testing whether dropping one of the two
from the feature set changes performance meaningfully, before moving
to the production Random Forest and XGBoost models specified in the
project architecture.
