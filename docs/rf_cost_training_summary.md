# Random Forest Cost Model — Training Summary

**Model:** `RandomForestRegressor` (scikit-learn 1.5.1)
**Target:** `cost_per_unit_usd` — packaging cost per unit, in USD
**Notebook:** `ml/notebooks/03_rf_cost_model.ipynb`
**Artifacts:** `ml/models/rf_cost.joblib` (deployable pipeline), `ml/models/RandomForestRegressor_cost_per_unit_usd_v1.pkl` (versioned model), `ml/experiments/metadata/RandomForestRegressor__cost_per_unit_usd__v1__20261004_171625.json`
**Metrics:** `ml/metrics/rf_cost_metrics.csv`

## 1. Features and Target

- **Features:** the 31 columns produced by the saved preprocessing pipeline
  (`models/preprocessing/preprocessing_pipeline.pkl`): 14 scaled numeric material
  properties, one-hot `material_type`, `packaging_type`, `supplier_region`, and ordinal
  `recyclability_category`. Same feature set as the baseline models (feature set v1).
- **Target:** `cost_per_unit_usd`, range $0.21–$25.95, mean $8.94.
- **Leakage check:** an automated assertion confirms neither target
  (`cost_per_unit_usd`, `co2_emission_per_kg`) nor any engineered index built from them
  is among the input features.
- **Product attributes not used:** `products.csv` has no key linking products to
  materials, and cost is a material property, so the model uses material features only.
  Product attributes enter later, in the recommendation engine.
- **Units:** the source data is in USD; kept as USD (no exchange rate in the data, and a
  constant conversion would not change model quality).

## 2. Configuration

| Hyperparameter | Value | Reason |
|---|---|---|
| n_estimators | 300 | Well past the point where out-of-bag score stabilises |
| max_depth | None | Standard RF default; averaging controls overfitting |
| min_samples_leaf | 1 | Default |
| max_features | 1.0 | scikit-learn default for regression |
| random_state | 42 | Reproducibility |
| n_jobs | -1 | Use all CPU cores |

Initial (untuned) configuration; tuning is a separate module.

## 3. Training Procedure

- Same split as the baselines: 80/20, `random_state=42` → 322 train / 81 test rows.
- Preprocessing pipeline fitted on training data only (module 7) and reused unchanged.
- 5-fold cross-validation on the training set (same folds as the baselines), then
  fit on the full training set and evaluated once on the held-out test set.
- **Convergence:** out-of-bag R² is flat as trees are added (0.9958 at 25 trees,
  0.9948 at 300, 0.9950 at 500), so the forest is stable at 300 trees.
- Logged through `run_experiment()` in `ml/training/train_model.py`.

## 4. Results

| Fold | MAE | RMSE | R² |
|---|---|---|---|
| 1 | 0.307 | 0.738 | 0.9865 |
| 2 | 0.251 | 0.384 | 0.9972 |
| 3 | 0.241 | 0.366 | 0.9974 |
| 4 | 0.161 | 0.262 | 0.9988 |
| 5 | 0.274 | 0.647 | 0.9907 |
| **CV mean** | **0.247** | **0.480** | **0.9941** |
| **Test set** | **0.189** | **0.310** | **0.9980** |

## 5. Comparison with Baselines (same test set)

| Model | Test MAE | Test RMSE | Test R² |
|---|---|---|---|
| Material-type average (naive reference) | 1.548 | 2.843 | 0.8306 |
| Linear Regression (baseline v1) | 0.333 | 0.404 | 0.9966 |
| **Random Forest** | **0.189** | **0.310** | **0.9980** |

- On the test set, Random Forest improves on the baseline in every metric:
  **43% lower MAE** and **23% lower RMSE**.
- In cross-validation the picture is mixed: RF has a much lower MAE (0.247 vs 0.357)
  but a slightly higher RMSE (0.480 vs 0.442) and R² (0.9941 vs 0.9960). RF is more
  accurate on typical materials but makes a few larger errors (see section 7).

## 6. Error by Material Type (test set)

| Material type | Mean abs. error ($) | Max abs. error ($) | Test rows |
|---|---|---|---|
| Cardboard | 0.153 | 1.101 | 33 |
| Paper/Bio-Based | 0.473 | 0.972 | 6 |
| Plastic | 0.156 | 0.654 | 37 |
| Steel | 0.329 | 0.807 | 5 |

## 7. Feature Importance and Limitations

Top features: `reusability_percent` (0.496), `waste_reduction_impact_percent` (0.286),
`total_material_weight_tons` (0.135) — together ~92% of total importance.

**Limitations:**
- **Occasional large misses on boundary materials.** In cross-validation, MAT_0019
  (plastic foldable container, $12.14) was predicted at $6.92 and MAT_0014 (paper filler,
  $2.34) at $6.80. Both have `waste_reduction_impact_percent` = 70, at the edge of their
  group's range, so the forest's numeric splits place them in the wrong price group.
  Linear Regression relies more on the category columns and does not make these errors.
  Candidate fixes for the tuning module: lower `max_features` (forces some splits onto
  category columns) and `min_samples_leaf` > 1.
- **Small data:** 403 materials; Paper/Bio-Based and Steel have only 6 and 5 test rows,
  so their per-type errors are less reliable.
- **No extrapolation:** tree models cannot predict outside the cost range seen in
  training ($0.21–$25.95).
- **Material features only:** product attributes are not yet part of the cost model.

## 8. Using the Model (backend inference)

`rf_cost.joblib` is a scikit-learn `Pipeline` (fitted preprocessor + fitted forest).
It takes raw material rows (same columns as `data/processed/materials.csv`) and
returns cost in USD:

```python
import joblib
model = joblib.load("ml/models/rf_cost.joblib")
predicted_cost = model.predict(new_materials_df)
```

Requires scikit-learn 1.5.1 (pinned in `environments/requirements.txt`).