# Data Dictionary — EcoPackAI Database

GENERATED from the ORM models in `backend/models/` by `python backend/manage.py data-dictionary`. Do not edit by hand.
Column names match `data/processed/materials.csv` and `products.csv`; the dataset-level dictionary (encoded/engineered columns) is `docs/data_dictionary_v2.xlsx`.

| Table | Purpose |
|---|---|
| `materials` | Packaging material catalogue (403 materials) |
| `prediction_history` | One row per material predicted by /predict |
| `products` | Products to package (1,500 products) |
| `recommendation_runs` | One row per /recommend request |
| `recommendation_logs` | Ranked materials per recommendation run (links products and materials) |

## Table: materials

Packaging material catalogue (403 materials)

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| material_id | VARCHAR(20) | no | PK | Unique material identifier, e.g. MAT_0001 |
| packaging_type | VARCHAR(100) | no |  | Specific packaging form (6 values) |
| material_type | VARCHAR(50) | no |  | Cardboard, Plastic, Paper/Bio-Based or Steel |
| suitable_product_categories | TEXT | no |  | Comma-separated product groups the material suits |
| recommended_packaging_use_cases | TEXT | no |  | Typical use case (free text) |
| supplier_region | VARCHAR(50) | no |  | EMEA, APAC, AMERICAS, ROW, LATAM or EU |
| recyclability_percent | FLOAT | no |  | % of material recyclable (0-100) |
| recyclability_category | VARCHAR(20) | no |  | Low, Medium or High |
| recycled_content_percent | FLOAT | no |  | % made from recycled input (0-100) |
| reusability_percent | FLOAT | no |  | % reuse potential (0-100) |
| biodegradation_time_days | FLOAT | no |  | Days to decompose |
| end_of_life_disposal_percent | FLOAT | no |  | % sent to disposal (0-100) |
| carbon_footprint_kg_co2_per_unit | FLOAT | no |  | CO2 per packaging unit (kg) |
| co2_emission_per_kg | FLOAT | no |  | CO2 per kg of material (target of the CO2 model) |
| waste_reduction_impact_percent | FLOAT | no |  | Estimated waste reduction (0-100) |
| sustainability_target_progress_percent | FLOAT | no |  | Progress toward sustainability goals (0-100) |
| load_handling_score | FLOAT | no |  | Load-bearing capability (1-10) |
| moisture_resistance_score | FLOAT | no |  | Resistance to moisture (1-10) |
| thermal_resistance_score | FLOAT | no |  | Resistance to temperature (1-10) |
| cost_per_unit_usd | FLOAT | no |  | Price per packaging unit in USD (target of the cost model) |
| annual_usage_units | FLOAT | no |  | Units used annually |
| total_material_weight_tons | FLOAT | no |  | Total annual material weight (tons) |
| supplier_sustainability_compliance_percent | FLOAT | no |  | Supplier compliance rating (0-100) |

## Table: prediction_history

One row per material predicted by /predict

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| id | INTEGER | no | PK | Row identifier |
| request_id | VARCHAR(64) | no | indexed | API request ID (X-Request-ID) |
| material_id | VARCHAR(50) | yes |  | material_id sent by the client (may be a new material) |
| input_hash | VARCHAR(64) | no | indexed | SHA-256 of the material attributes |
| inputs | JSON | no |  | Material attributes sent |
| predicted_cost_usd | FLOAT | no |  | Predicted cost per unit (USD) |
| predicted_co2_per_kg | FLOAT | no |  | Predicted CO2 per kg |
| cost_model_version | VARCHAR(50) | no |  | Cost model name and version |
| co2_model_version | VARCHAR(50) | no |  | CO2 model name and version |
| cached | BOOLEAN | no |  | True if served from the response cache |
| created_at | TIMESTAMP WITH TIME ZONE | no |  | When the prediction was made |

## Table: products

Products to package (1,500 products)

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| product_id | INTEGER | no | PK | Unique product identifier |
| product_name | VARCHAR(100) | no |  | Product name |
| category | VARCHAR(100) | no |  | Food, Electronics, Cosmetics, Paper Product, Pharmacy or Drinkware |
| product_weight_kg | FLOAT | no |  | Net product weight (kg) |
| fragility_index | INTEGER | no |  | Handling care required, 1 (low) to 5 (high) |
| shipping_type | VARCHAR(50) | no |  | Air, Road or Sea |

## Table: recommendation_runs

One row per /recommend request

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| run_id | INTEGER | no | PK | Run identifier |
| request_id | VARCHAR(64) | no | indexed | API request ID (X-Request-ID) |
| product_id | INTEGER | yes | FK → products.product_id, indexed | Product from the products table; NULL for a product sent inline |
| product_snapshot | JSON | no |  | Product attributes used for the ranking |
| mode | VARCHAR(30) | no |  | balanced, sustainability_first or cost_first |
| top_n | INTEGER | no |  | Number of materials requested |
| n_candidates | INTEGER | no |  | Materials that passed the business constraints |
| status | VARCHAR(30) | no |  | ok or no_valid_material |
| cost_model_version | VARCHAR(50) | no |  | Cost model name and version |
| co2_model_version | VARCHAR(50) | no |  | CO2 model name and version |
| cached | BOOLEAN | no |  | True if served from the response cache |
| created_at | TIMESTAMP WITH TIME ZONE | no |  | When the run happened |

## Table: recommendation_logs

Ranked materials per recommendation run (links products and materials)

| Column | Type | Nullable | Key | Description |
|---|---|---|---|---|
| rec_id | INTEGER | no | PK | Unique identifier for each recommendation record |
| run_id | INTEGER | no | FK → recommendation_runs.run_id, indexed | Run this result belongs to |
| product_id | INTEGER | yes | FK → products.product_id, indexed | Product the recommendation is for (NULL for an inline product) |
| recommended_material_id | VARCHAR(20) | no | FK → materials.material_id, indexed | Recommended material |
| cost_prediction | FLOAT | no |  | Predicted cost per unit (USD) from the Random Forest model |
| co2_prediction | FLOAT | no |  | Predicted CO2 per kg from the XGBoost model |
| final_score | FLOAT | no |  | Weighted ranking score (0-100) |
| material_rank | INTEGER | no |  | 1 = best |
| created_at | TIMESTAMP WITH TIME ZONE | no |  | When the recommendation was generated |

## Relationships

- `recommendation_runs.product_id` → `products` (NULL when the product was sent inline)
- `recommendation_logs.run_id` → `recommendation_runs` (one run has many ranked materials; deleting a run deletes its rows)
- `recommendation_logs.product_id` → `products` and `recommendation_logs.recommended_material_id` → `materials`: this table is the many-to-many link between products and materials
- `prediction_history` stores what clients sent, which may be new materials, so it has no foreign key to `materials`
