-- EcoPackAI database schema (PostgreSQL)
-- GENERATED from backend/models by: python backend/manage.py export-schema
-- Do not edit by hand. Tables are created by the Alembic migrations in backend/migrations/.

CREATE TABLE materials (
	material_id VARCHAR(20) NOT NULL, 
	packaging_type VARCHAR(100) NOT NULL, 
	material_type VARCHAR(50) NOT NULL, 
	suitable_product_categories TEXT NOT NULL, 
	recommended_packaging_use_cases TEXT NOT NULL, 
	supplier_region VARCHAR(50) NOT NULL, 
	recyclability_percent FLOAT NOT NULL, 
	recyclability_category VARCHAR(20) NOT NULL, 
	recycled_content_percent FLOAT NOT NULL, 
	reusability_percent FLOAT NOT NULL, 
	biodegradation_time_days FLOAT NOT NULL, 
	end_of_life_disposal_percent FLOAT NOT NULL, 
	carbon_footprint_kg_co2_per_unit FLOAT NOT NULL, 
	co2_emission_per_kg FLOAT NOT NULL, 
	waste_reduction_impact_percent FLOAT NOT NULL, 
	sustainability_target_progress_percent FLOAT NOT NULL, 
	load_handling_score FLOAT NOT NULL, 
	moisture_resistance_score FLOAT NOT NULL, 
	thermal_resistance_score FLOAT NOT NULL, 
	cost_per_unit_usd FLOAT NOT NULL, 
	annual_usage_units FLOAT NOT NULL, 
	total_material_weight_tons FLOAT NOT NULL, 
	supplier_sustainability_compliance_percent FLOAT NOT NULL, 
	PRIMARY KEY (material_id)
);

CREATE TABLE prediction_history (
	id SERIAL NOT NULL, 
	request_id VARCHAR(64) NOT NULL, 
	material_id VARCHAR(50), 
	input_hash VARCHAR(64) NOT NULL, 
	inputs JSON NOT NULL, 
	predicted_cost_usd FLOAT NOT NULL, 
	predicted_co2_per_kg FLOAT NOT NULL, 
	cost_model_version VARCHAR(50) NOT NULL, 
	co2_model_version VARCHAR(50) NOT NULL, 
	cached BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_prediction_history_input_hash ON prediction_history (input_hash);
CREATE INDEX ix_prediction_history_request_id ON prediction_history (request_id);

CREATE TABLE products (
	product_id SERIAL NOT NULL, 
	product_name VARCHAR(100) NOT NULL, 
	category VARCHAR(100) NOT NULL, 
	product_weight_kg FLOAT NOT NULL, 
	fragility_index INTEGER NOT NULL, 
	shipping_type VARCHAR(50) NOT NULL, 
	PRIMARY KEY (product_id)
);

CREATE TABLE recommendation_runs (
	run_id SERIAL NOT NULL, 
	request_id VARCHAR(64) NOT NULL, 
	product_id INTEGER, 
	product_snapshot JSON NOT NULL, 
	mode VARCHAR(30) NOT NULL, 
	top_n INTEGER NOT NULL, 
	n_candidates INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	cost_model_version VARCHAR(50) NOT NULL, 
	co2_model_version VARCHAR(50) NOT NULL, 
	cached BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (run_id), 
	FOREIGN KEY(product_id) REFERENCES products (product_id)
);
CREATE INDEX ix_recommendation_runs_product_id ON recommendation_runs (product_id);
CREATE INDEX ix_recommendation_runs_request_id ON recommendation_runs (request_id);

CREATE TABLE recommendation_logs (
	rec_id SERIAL NOT NULL, 
	run_id INTEGER NOT NULL, 
	product_id INTEGER, 
	recommended_material_id VARCHAR(20) NOT NULL, 
	cost_prediction FLOAT NOT NULL, 
	co2_prediction FLOAT NOT NULL, 
	final_score FLOAT NOT NULL, 
	material_rank INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (rec_id), 
	FOREIGN KEY(run_id) REFERENCES recommendation_runs (run_id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (product_id), 
	FOREIGN KEY(recommended_material_id) REFERENCES materials (material_id)
);
CREATE INDEX ix_recommendation_logs_product_id ON recommendation_logs (product_id);
CREATE INDEX ix_recommendation_logs_recommended_material_id ON recommendation_logs (recommended_material_id);
CREATE INDEX ix_recommendation_logs_run_id ON recommendation_logs (run_id);
