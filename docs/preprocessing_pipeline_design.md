# Preprocessing Pipeline Design — EcoPackAI

Explains the design of `models/preprocessing/preprocessing_pipeline.pkl`,
a fitted `sklearn.compose.ColumnTransformer` that consistently
transforms raw materials data into model-ready features for both
training and future inference.

## Why a Single Pipeline Object

Earlier preprocessing work (see `encoding_normalization_report.md`)
applied `OneHotEncoder` and `MinMaxScaler` manually, as separate steps
saved to separate `.pkl` files. This works, but requires anyone
reusing it to remember the exact order of operations by hand.

A `ColumnTransformer` bundles imputation, encoding, and scaling for
every column group into a single fitted object. Loading this one file
and calling `.transform()` guarantees training and inference apply
identical transformations, in the correct order, every time.

## Structure

Three parallel branches, each a `sklearn.pipeline.Pipeline`:

1. **Numeric branch** (`num`): `SimpleImputer(strategy='median')` ->
   `StandardScaler()`. Median imputation was chosen for consistency
   with the earlier defensive imputer setup in Module 2, since it is
   robust to the extreme outliers already found in this dataset (e.g.
   `biodegradation_time_days`). `StandardScaler` (zero mean, unit
   variance) was used here rather than `MinMaxScaler`, since this
   pipeline is a from-scratch rebuild intended to demonstrate both
   scaling approaches across the project.

2. **Nominal branch** (`nom`): `SimpleImputer(strategy='most_frequent')`
   -> `OneHotEncoder(handle_unknown='ignore')`. `handle_unknown='ignore'`
   ensures that if a future material arrives with a packaging type or
   supplier region not seen during training, the pipeline will not
   crash — it will just encode all-zero for that column instead.

3. **Ordinal branch** (`ord`): `SimpleImputer(strategy='most_frequent')`
   -> `OrdinalEncoder(categories=[['Low', 'Medium', 'High']])`. The
   explicit category order is passed in directly, avoiding the risk
   of `OrdinalEncoder` defaulting to alphabetical order (which would
   incorrectly rank High < Low < Medium).

`remainder='drop'` on the `ColumnTransformer` ensures identifiers,
free-text fields, and the two prediction targets are never accidentally
included as features.

## Fitting Discipline

The pipeline was fit **only** on the training split (`train_df`,
80% of the data) using `.fit_transform()`. The test split (`test_df`)
was only ever passed through `.transform()`, never `.fit()`, so no
information from the test set (e.g. its own medians or category
frequencies) leaked into the learned parameters. This preserves a
fair, honest evaluation later during model testing.

## Output

- 18 usable input columns -> 31 output columns after transformation
  (expansion comes from one-hot encoding of `material_type`,
  `packaging_type`, and `supplier_region`)
- Verified via `data/model_ready/sample_transformed.csv`, a 10-row
  snapshot of the actual transformed training data

## Reuse

To apply this pipeline to new data at inference time:

```python
import joblib
preprocessor = joblib.load('models/preprocessing/preprocessing_pipeline.pkl')
new_data_transformed = preprocessor.transform(new_data)
```

No re-fitting is required or should ever be performed on new data —
doing so would break consistency with how the trained models expect
their inputs to be shaped.
