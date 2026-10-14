# Baseline Model Summary — EcoPackAI

## Models Selected

| Target | Model | Rationale |
|---|---|---|
| `cost_per_unit_usd` | Linear Regression | Simple, interpretable baseline. Coefficients directly show which features drive cost, useful for a first-pass sanity check before trying more complex models. |
| `co2_emission_per_kg` | Decision Tree Regressor | Simple, interpretable baseline that can capture non-linear splits (e.g. material-type-driven thresholds) without needing feature scaling assumptions that linear models require. |

Both models were kept at default/minimal hyperparameters, as intended
for a baseline — the only parameter set explicitly was `random_state=42`
on the Decision Tree, to make split behavior reproducible.

## Training Setup

- **Features:** 31 columns after the `ColumnTransformer` pipeline
  (see `docs/preprocessing_columns.md`), built from the materials
  dataset only.
- **Targets:** real-world `cost_per_unit_usd` (USD) and
  `co2_emission_per_kg` (kg CO2), not scaled versions — see
  `docs/data_dictionary_features_targets.md` for the leakage exclusions
  applied when selecting features.
- **Cross-validation:** 5-fold, applied only to the training split
  (322 materials). The held-out test split (81 materials) was never
  used during training or cross-validation, only for final evaluation.

## Model Assumptions & Limitations

**Linear Regression (cost):**
- Assumes a linear relationship between features and cost. Works well
  here because material type strongly and consistently separates cost
  ranges (see `docs/baseline_evaluation_report.md` for the full
  explanation).
- Sensitive to multicollinearity: `material_type` and `packaging_type`
  were found to be perfectly correlated in this dataset (every
  material type maps to exactly one packaging type), so the model
  effectively double-counts the same signal through two sets of
  one-hot columns. This does not break the model here, but would be
  worth resolving (e.g. dropping one of the two columns) before adding
  more features.

**Decision Tree Regressor (CO2):**
- No linearity assumption, but prone to overfitting on small datasets
  if left unconstrained (no `max_depth` was set here, consistent with
  keeping this a true baseline).
- Like the linear model, benefits heavily from `material_type` being a
  strong natural predictor of CO2 emissions in this dataset.

## Next Steps

These baselines establish a strong performance floor. The main
project architecture specifies Random Forest (cost) and XGBoost (CO2)
as the production models — see `docs/final_model_evaluation.md` (once
created) for how those compare against these baselines.
