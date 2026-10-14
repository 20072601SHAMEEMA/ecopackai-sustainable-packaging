# Model Version History — EcoPackAI

Tracks every trained model version, its configuration, and its
performance, using the standardized `run_experiment()` workflow in
`ml/training/train_model.py`.

## Naming Convention

```
{model_name}_{target_variable}_v{version}.pkl
```

Example: `LinearRegression_cost_per_unit_usd_v1.pkl`

Each model artifact has a matching metadata JSON file in
`ml/experiments/metadata/`, named:

```
{model_name}__{target_variable}__v{version}__{timestamp}.json
```

Version numbers increment automatically per model+target combination
every time `run_experiment()` is called, so a new training run never
silently overwrites a previous version's artifact or metadata.

## Version Log

### v1 — LinearRegression (cost_per_unit_usd)

- **Date:** 2026-10-04
- **Dataset version:** v1
- **Feature set version:** v1 (31 features via `ColumnTransformer`)
- **Hyperparameters:** default (`fit_intercept=True`)
- **Cross-validation (5-fold):** MAE 0.357, RMSE 0.442, R2 0.996
- **Test set:** MAE 0.333, RMSE 0.404, R2 0.997
- **Notes:** Baseline model. Strong performance traced to
  `material_type` tightly clustering cost ranges; found
  `material_type` and `packaging_type` to be perfectly collinear in
  this dataset (see `docs/baseline_evaluation_report.md`).
- **Artifact:** `ml/models/LinearRegression_cost_per_unit_usd_v1.pkl`

### v1 — DecisionTreeRegressor (co2_emission_per_kg)

- **Date:** 2026-10-04
- **Dataset version:** v1
- **Feature set version:** v1 (31 features via `ColumnTransformer`)
- **Hyperparameters:** `random_state=42`, no `max_depth` set
- **Cross-validation (5-fold):** MAE 0.055, RMSE 0.082, R2 0.986
- **Test set:** MAE 0.051, RMSE 0.078, R2 0.987
- **Notes:** Baseline model. Also benefits from material-type-driven
  thresholds in CO2 emissions.
- **Artifact:** `ml/models/DecisionTreeRegressor_co2_emission_per_kg_v1.pkl`

### v1 — RandomForestRegressor (cost_per_unit_usd)

- **Date:** 2026-10-04
- **Dataset version:** v1
- **Feature set version:** v1 (31 features via `ColumnTransformer`)
- **Hyperparameters:** `n_estimators=300`, `max_depth=None`, `min_samples_leaf=1`, `max_features=1.0`, `random_state=42`
- **Cross-validation (5-fold):** MAE 0.247, RMSE 0.480, R2 0.994
- **Test set:** MAE 0.189, RMSE 0.310, R2 0.998
- **Notes:** Production cost model. Beats the Linear Regression baseline on all test
  metrics (MAE -43%); higher CV RMSE due to two boundary materials (see
  `docs/rf_cost_training_summary.md`).
- **Experiment record:** `ml/experiments/metadata/RandomForestRegressor__cost_per_unit_usd__v1__20261004_171625.json`
- **Artifact:** `ml/models/RandomForestRegressor_cost_per_unit_usd_v1.pkl`; deployable pipeline `ml/models/rf_cost.joblib`

### v1 — XGBRegressor (co2_emission_per_kg)

- **Date:** 2026-10-04
- **Dataset version:** v1
- **Feature set version:** v1 (31 features via `ColumnTransformer`)
- **Hyperparameters:** `objective=reg:squarederror`, `n_estimators=200`, `max_depth=3`, `learning_rate=0.03`, `subsample=0.8`, `colsample_bytree=0.5`, `random_state=42`
- **Cross-validation (5-fold):** MAE 0.049, RMSE 0.083, R2 0.986
- **Test set:** MAE 0.036, RMSE 0.054, R2 0.994
- **Notes:** Production CO2 model. Test RMSE 31% lower than the Decision Tree baseline;
  CV RMSE on par. Does not beat the material-type average (test RMSE 0.050): CO2 is
  determined by material type in this dataset (see `docs/xgb_co2_training_summary.md`).
- **Experiment record:** `ml/experiments/metadata/XGBRegressor__co2_emission_per_kg__v1__20261004_185626.json`
- **Artifact:** `ml/models/XGBRegressor_co2_emission_per_kg_v1.pkl`; deployable pipeline `ml/models/xgb_co2.joblib`

## Planned Future Versions

| Version | Model | Target | Change |
|---|---|---|---|
| v1 | RandomForestRegressor | co2_emission_per_kg | Candidate replacement for XGBoost CO2: untuned RF scored better in final evaluation (test MAE 0.0350 vs 0.0358, CV RMSE 0.069 vs 0.083); see `docs/final_model_evaluation.md` |
| v2 | RandomForestRegressor | cost_per_unit_usd | Hyperparameter tuning (e.g. lower `max_features`, `min_samples_leaf` > 1) to reduce large errors on boundary materials |

## Backward Compatibility

All previous versions remain in `ml/models/` and are never deleted or
overwritten by later training runs, since version numbers increment
automatically. This allows any prior model to be reloaded and compared
against newer versions at any time.
