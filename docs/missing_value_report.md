# Missing Value Report — EcoPackAI

## Summary

Both processed datasets (`materials.csv`, `products.csv`) contain zero
missing values at the time of this preprocessing step. This is because
missing values were already resolved during the earlier ingestion/cleaning
stage (see `docs/data_validation_report.md`).

## Details

| Dataset | Missing Values Found (this stage) | Cause |
|---|---|---|
| materials.csv | 0 | One incomplete row (MAT_0404, 14/23 columns blank) was already removed during ingestion. |
| products.csv | 0 | No missing values were present in the raw file. |

## Strategy Applied (Defensive, for Future Data)

Although no imputation was needed on the current dataset, imputers were
set up and fitted so the pipeline can handle future data batches that do
contain gaps:

| Column Type | Strategy | Reasoning |
|---|---|---|
| Numeric | Median (`SimpleImputer(strategy="median")`) | Median is robust to outliers such as `biodegradation_time_days`, which has extreme high values for Steel. |
| Categorical | Most frequent (`SimpleImputer(strategy="most_frequent")`) | Fills gaps with the most common category, a reasonable default when no other signal is available. |

No rows were removed at this stage (the one row requiring removal was
handled earlier during ingestion, since more than half its values were
missing).

## Conclusion

The dataset entering feature engineering is fully complete, with no
missing values requiring imputation. The imputation pipeline is fitted
and ready to apply to new data if needed.