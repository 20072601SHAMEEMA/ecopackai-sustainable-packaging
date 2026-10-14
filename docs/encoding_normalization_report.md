# Encoding & Normalization Report — EcoPackAI

## Materials Dataset

### Categorical Encoding

| Column | Type | Method | Reasoning |
|---|---|---|---|
| `material_type` | Nominal | One-Hot Encoding | No natural order between Cardboard, Plastic, Paper/Bio-Based, Steel. |
| `packaging_type` | Nominal | One-Hot Encoding | No natural order between specific packaging forms. |
| `supplier_region` | Nominal | One-Hot Encoding | No natural order between regions (EMEA, APAC, AMERICAS, ROW, LATAM). |
| `recyclability_category` | Ordinal | Manual mapping (Low=0, Medium=1, High=2) | Has a genuine order. A plain `LabelEncoder` was avoided since it assigns codes alphabetically and would not preserve Low < Medium < High. |

Columns excluded from encoding: `material_id` (identifier, not a feature),
`suitable_product_categories` and `recommended_packaging_use_cases`
(free-text descriptions, not clean categories).

**Note:** the dataset contains no materials rated "Low" recyclability —
only Medium (198) and High (205) are present.

### Numeric Scaling

All 16 remaining numeric columns (e.g. `cost_per_unit_usd`,
`biodegradation_time_days`, `load_handling_score`) were scaled to a 0-1
range using `MinMaxScaler`. This was necessary because these columns
have very different original scales — for example `annual_usage_units`
ranges into the tens of thousands, while `load_handling_score` ranges
1-10. Without scaling, a model could wrongly treat larger-magnitude
columns as more important.

### Output

- Encoded dataset: `data/model_ready/materials_final_encoded.csv` (403 rows, 34 columns)
- One-hot encoder: `models/encoders/ohe_encoder.pkl`
- Scaler: `models/scalers/numeric_scaler.pkl`

## Products Dataset

### Categorical Encoding

| Column | Type | Method | Reasoning |
|---|---|---|---|
| `category` | Nominal | One-Hot Encoding | No natural order between product categories. |
| `shipping_type` | Nominal | One-Hot Encoding | No natural order between Air, Road, Sea. |

Columns excluded: `product_id`, `product_name` (identifiers, not features).

### Numeric Scaling

`product_weight_kg` and `fragility_index` were scaled to a 0-1 range
with `MinMaxScaler` for consistency, even though `fragility_index`'s
original range (1-5) is already fairly small.

### Output

- Encoded dataset: `data/model_ready/products_final_encoded.csv` (1500 rows, 12 columns)
- One-hot encoder: `models/encoders/ohe_encoder_products.pkl`
- Scaler: `models/scalers/numeric_scaler_products.pkl`

## Validation Checklist

- [x] No remaining missing values
- [x] Numeric features scaled 0-1
- [x] Categorical fields encoded
- [x] Encoders & scalers saved for inference
- [x] Final datasets exported
