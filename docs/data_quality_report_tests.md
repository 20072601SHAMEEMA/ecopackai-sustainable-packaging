# Data Quality Report — EcoPackAI

Results of running `tests/test_data_quality.py` against the real
processed dataset (`data/processed/materials.csv`), encoded dataset
(`data/model_ready/materials_final_encoded.csv`), and engineered
dataset (`data/model_ready/materials_with_features.csv`).

## Test Run Summary

```
============================= test session starts ==============================
collected 19 items

test_required_columns_present               PASSED
test_no_unexpected_row_count_drop            PASSED
test_no_nulls_in_mandatory_fields            PASSED
test_no_duplicate_material_ids               PASSED
test_no_fully_duplicate_rows                 PASSED
test_cost_is_positive                        PASSED
test_co2_emission_non_negative               PASSED
test_moisture_resistance_range               PASSED
test_thermal_resistance_range                PASSED
test_biodegradation_days_minimum             PASSED
test_percent_columns_in_range                PASSED
test_no_negative_weights                     PASSED
test_material_type_categories_valid          PASSED
test_recyclability_category_valid            PASSED
test_supplier_region_valid                   PASSED
test_recyclability_encoded_only_valid_values PASSED
test_scaled_columns_within_unit_range        PASSED
test_engineered_scores_in_range              PASSED
test_engineered_scores_no_nan_or_inf         PASSED

============================== 19 passed ==============================
```

## Result

All 19 tests passed on the first run. This is expected, since the
missing/incomplete row and category inconsistencies were already
resolved during the earlier ingestion and cleaning stage (see
`data_validation_report.md`), and the feature engineering formulas
were designed to mathematically guarantee a 0-100 output range
(see `feature_engineering_document.md`).

## Coverage

- **Structural:** required columns present, dataset non-empty
- **Cleanliness:** no nulls in mandatory fields, no duplicate IDs, no duplicate rows
- **Range:** cost, CO2, resistance scores, biodegradation days, all percentage columns, weights
- **Categorical:** material_type, recyclability_category, supplier_region all restricted to known values
- **Encoding:** recyclability encoding only contains 0/1/2, all scaled columns within 0-1
- **Feature engineering:** CII, CEI, MSS all within 0-100, no NaN or infinite values

## Notes

If new raw data is ingested in the future with different category
values, invalid ranges, or missing mandatory fields, these tests will
fail and flag exactly which rule was violated and on which column —
this is the intended purpose of maintaining this suite going forward.