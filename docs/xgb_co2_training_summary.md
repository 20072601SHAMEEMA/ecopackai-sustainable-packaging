# XGBoost CO2 Model — Training Summary

**Model:** `XGBRegressor` (xgboost 2.1.0, scikit-learn 1.5.1)
**Target:** `co2_emission_per_kg` — kg CO2 emitted per kg of packaging material
**Notebook:** `ml/notebooks/04_xgb_co2_model.ipynb`
**Artifacts:** `ml/models/xgb_co2.joblib` (deployable pipeline), `ml/models/XGBRegressor_co2_emission_per_kg_v1.pkl` (versioned model), `ml/experiments/metadata/XGBRegressor__co2_emission_per_kg__v1__20261004_185626.json`
**Metrics:** `ml/metrics/co2_metrics.csv` · **Feature importance:** `ml/reports/feature_importance.csv`

## 1. Inputs and Deviations from the Task Brief

- **Features:** the 31 columns from the saved preprocessing pipeline
  (`models/preprocessing/preprocessing_pipeline.pkl`), the same feature set (v1) as
  the baseline and Random Forest models.
- **CO2 per kg excluded as a feature:** the brief lists it as an input, but it is the
  prediction target; using it would be target leakage. An automated assertion
  confirms neither target is among the features.
- **Raw data, not X_raw.csv:** the saved pipeline expects raw material columns, while
  `X_raw.csv` is already encoded and scaled. The pipeline is applied to
  `data/processed/materials.csv`, as in the Random Forest task.
- **Target per kg, not per unit:** kept as `co2_emission_per_kg` so results are directly
  comparable with the Decision Tree baseline.
- **Product attributes not used:** no key links products to materials; product
  attributes enter in the recommendation engine.
- **Output folders:** `ml/models/`, `ml/metrics/`, `ml/reports/` (project layout);
  file names as specified in the brief.

## 2. Configuration

| Hyperparameter | Value | Reason |
|---|---|---|
| objective | reg:squarederror | Required by brief; squared-error regression |
| n_estimators | 200 | Validation loss stops improving after ~150 rounds |
| max_depth | 3 | Small trees; less overfitting on 322 rows |
| learning_rate | 0.03 | Small correction steps |
| subsample | 0.8 | Row sampling per tree for variety |
| colsample_bytree | 0.5 | Forces trees to use the material-type columns (see below) |
| random_state | 42 | Reproducibility |

**colsample_bytree** was chosen with 5-fold cross-validation on the training set only
(0.5 / 0.8 / 1.0 compared; CV RMSE 0.084 / 0.094 / 0.10). With all columns available,
trees split on numeric features where Steel overlaps with plastic totes
(reusability 91–100% vs 90–100%), producing large errors on Steel (e.g. 2.85 predicted
as 1.85). Restricting columns per tree makes many trees split on `material_type`.

## 3. Training and Convergence

- 80/20 split, `random_state=42` → 322 train / 81 test (same as all other models).
- Loss monitored on a validation set carved from the training data (the test set is
  never used for decisions):

| Round | Train RMSE | Validation RMSE |
|---|---|---|
| 1 | 0.697 | 0.747 |
| 50 | 0.178 | 0.195 |
| 100 | 0.066 | 0.091 |
| 200 | 0.037 | 0.084 |
| 300 | 0.030 | 0.085 |
| 500 | 0.022 | 0.085 |

Validation RMSE reaches its minimum (0.0827) at round 148 and is flat afterwards while
training RMSE keeps falling, so additional rounds would only memorise the training
data. Final model: 200 rounds.

## 4. Results

| Fold | MAE | RMSE | R² |
|---|---|---|---|
| 1 | 0.0458 | 0.0758 | 0.9856 |
| 2 | 0.0465 | 0.0819 | 0.9892 |
| 3 | 0.0581 | 0.0882 | 0.9846 |
| 4 | 0.0543 | 0.1112 | 0.9806 |
| 5 | 0.0398 | 0.0594 | 0.9922 |
| **CV mean** | **0.0489** | **0.0833** | **0.9864** |
| **Test set** | **0.0358** | **0.0537** | **0.9938** |

## 5. Comparison with Baselines (same test set)

| Model | Test MAE | Test RMSE | Test R² | CV RMSE |
|---|---|---|---|---|
| Material-type average (naive reference) | 0.0333 | 0.0503 | 0.9945 | 0.0591 |
| Decision Tree (baseline v1) | 0.0507 | 0.0780 | 0.9869 | 0.0823 |
| **XGBoost** | **0.0358** | **0.0537** | **0.9938** | **0.0833** |

- **Acceptance criterion met:** test RMSE improves on the Decision Tree baseline by
  **31%** (0.0780 → 0.0537); MAE by 29%.
- In cross-validation, RMSE is on par with the Decision Tree (0.0833 vs 0.0823) while MAE
  is clearly lower (0.0489 vs 0.0546).
- **Neither model beats the material-type average.** CO2 per kg falls in narrow,
  non-overlapping bands per material type (Paper 0.28–0.33, Cardboard 0.47–0.55,
  Plastic 1.35–1.64, Steel 2.71–3.25), and within a type it is essentially
  uncorrelated with every other column (|r| ≤ 0.05 for Plastic). The remaining
  variation is not explained by the available features.

## 6. Error by Material Type (test set)

| Material type | Mean abs. error | Max abs. error | Test rows |
|---|---|---|---|
| Cardboard | 0.0147 | 0.0871 | 33 |
| Paper/Bio-Based | 0.0166 | 0.0292 | 6 |
| Plastic | 0.0544 | 0.1496 | 37 |
| Steel | 0.0611 | 0.2270 | 5 |

## 7. Feature Importance (gain)

| Rank | Feature | Gain |
|---|---|---|
| 1 | moisture_resistance_score | 0.204 |
| 2 | material_type_Plastic | 0.199 |
| 3 | end_of_life_disposal_percent | 0.161 |
| 4 | biodegradation_time_days | 0.110 |
| 5 | material_type_Steel | 0.092 |

Full list: `ml/reports/feature_importance.csv`. The top features are those that separate
material types; this agrees with the finding that material type drives CO2.

## 8. Limitations and Next Steps

- CO2 prediction is bounded by the data: the model reliably identifies the material
  type's CO2 band but cannot explain variation within a type. Better within-type
  prediction needs new information (manufacturing process, energy source, transport
  distance), not a different algorithm.
- For recommendations this is sufficient: prediction errors (~0.04 kg/kg) are far
  smaller than the gaps between material types (0.2–1.5 kg/kg), so material rankings
  by CO2 are reliable.
- Small data: 403 materials; Steel and Paper have only 5 and 6 test rows.

## 9. Using the Model (backend inference)

```python
import joblib
model = joblib.load("ml/models/xgb_co2.joblib")
predicted_co2 = model.predict(new_materials_df)   # raw material rows → kg CO2 per kg
```

Requires scikit-learn 1.5.1 and xgboost 2.1.0 (pinned in `environments/requirements.txt`).