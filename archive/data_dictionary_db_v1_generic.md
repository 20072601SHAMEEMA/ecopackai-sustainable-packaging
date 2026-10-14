# Data Dictionary — EcoPackAI

Describes every column in the `ecopackai_db` schema: its table, datatype, accepted values, and purpose.

## Table: materials

| Column | Type | Accepted Values / Notes | Purpose |
|---|---|---|---|
| material_id | INT (SERIAL) | Auto-incrementing | Unique identifier for each material |
| material_type | VARCHAR(100) | e.g. paper, bioplastic, PLA, cardboard, sugarcane | Name of the packaging material |
| strength_mpa | FLOAT | >= 0 | Mechanical strength capacity, in megapascals |
| weight_capacity | FLOAT | >= 0, kg | Maximum load the material can support |
| biodegradability_percent | FLOAT | 0–100 | % of material that breaks down naturally |
| co2_emission_score | FLOAT | >= 0 | Carbon footprint index for producing/using the material |
| recyclability_percent | FLOAT | 0–100 | % of the material that can be recycled/reused |
| cost_per_kg | FLOAT | >= 0 | Price per kilogram (INR or USD, kept consistent across dataset) |
| industry_use_case | VARCHAR(200) | e.g. Electronics, Food, Cosmetics, Pharmacy | Industries this material is typically used in |

## Table: products

| Column | Type | Accepted Values / Notes | Purpose |
|---|---|---|---|
| product_id | INT (SERIAL) | Auto-incrementing | Unique identifier for each product |
| product_name | VARCHAR(100) | Free text | Name/label of the product |
| category | VARCHAR(100) | e.g. Electronics, Food, Cosmetics | Product category |
| product_weight | FLOAT | >= 0, kg | Net weight of the item |
| fragility_index | INT | 1 (low) – 5 (high), scale can be adjusted | How much handling care the product needs |
| shipping_type | VARCHAR(50) | Air / Road / Sea | Mode of shipping used |

## Table: recommendation_logs

| Column | Type | Accepted Values / Notes | Purpose |
|---|---|---|---|
| rec_id | INT (SERIAL) | Auto-incrementing | Unique identifier for each prediction record |
| product_id | INT | FK -> products.product_id | Which product this recommendation is for |
| recommended_material_id | INT | FK -> materials.material_id | Which material was recommended |
| cost_prediction | FLOAT | >= 0 | Predicted cost from the Random Forest model |
| co2_prediction | FLOAT | >= 0 | Predicted CO2 impact from the XGBoost model |
| material_rank | INT | 1 = best, ascending | Rank position of this material for the given product |
| created_at | TIMESTAMP | Default: current timestamp | When the recommendation was generated |

