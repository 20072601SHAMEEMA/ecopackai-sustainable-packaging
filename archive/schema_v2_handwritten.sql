-- EcoPackAI Database Schema (v2 — updated to match real provided datasets)
-- Database: ecopackai_db

CREATE TABLE materials (
    material_id VARCHAR(20) PRIMARY KEY,          -- e.g. MAT_0001 (kept as given, not auto-increment)
    packaging_type VARCHAR(100) NOT NULL,
    material_type VARCHAR(50) NOT NULL,           -- Cardboard / Plastic / Steel / Paper/Bio-Based
    suitable_product_categories TEXT,             -- comma-separated in source; kept as text
    recommended_packaging_use_cases TEXT,
    supplier_region VARCHAR(50),                  -- EMEA / APAC / AMERICAS / ROW
    recyclability_percent FLOAT,
    recyclability_category VARCHAR(20),           -- High / Medium / Low
    recycled_content_percent FLOAT,
    reusability_percent FLOAT,
    biodegradation_time_days FLOAT,
    end_of_life_disposal_percent FLOAT,
    carbon_footprint_kg_co2_per_unit FLOAT,
    co2_emission_per_kg FLOAT,
    waste_reduction_impact_percent FLOAT,
    sustainability_target_progress_percent FLOAT,
    load_handling_score FLOAT,
    moisture_resistance_score FLOAT,
    thermal_resistance_score FLOAT,
    cost_per_unit_usd FLOAT,
    annual_usage_units FLOAT,
    total_material_weight_tons FLOAT,
    supplier_sustainability_compliance_percent FLOAT
);

CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(100),
    category VARCHAR(100),
    product_weight_kg FLOAT,
    fragility_index INT,
    shipping_type VARCHAR(50)                     -- Air / Road / Sea
);

CREATE TABLE recommendation_logs (
    rec_id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(product_id),
    recommended_material_id VARCHAR(20) REFERENCES materials(material_id),
    cost_prediction FLOAT,
    co2_prediction FLOAT,
    material_rank INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

