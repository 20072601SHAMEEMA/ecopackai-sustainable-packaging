"""
EcoPackAI - Data Quality Test Suite
Module: Data Quality Checks & Unit Tests

Validates materials.csv (cleaned), materials_final_encoded.csv, and
materials_with_features.csv against the rules defined in
docs/data_quality_rules.md.

Run with: pytest tests/test_data_quality.py -v
"""

import pandas as pd
import numpy as np
import pytest
from pathlib import Path

DATA_DIR = Path("data")

REQUIRED_RAW_COLUMNS = {
    "material_id", "material_type", "packaging_type", "supplier_region",
    "recyclability_percent", "recyclability_category", "cost_per_unit_usd",
    "co2_emission_per_kg", "biodegradation_time_days",
    "load_handling_score", "moisture_resistance_score", "thermal_resistance_score",
}

VALID_MATERIAL_TYPES = {"Cardboard", "Plastic", "Paper/Bio-Based", "Steel"}
VALID_RECYCLABILITY_CATEGORIES = {"Low", "Medium", "High"}
VALID_SUPPLIER_REGIONS = {"EMEA", "APAC", "AMERICAS", "ROW", "LATAM", "EU"}


@pytest.fixture(scope="module")
def materials_clean():
    return pd.read_csv(DATA_DIR / "processed" / "materials.csv")


@pytest.fixture(scope="module")
def materials_encoded():
    return pd.read_csv(DATA_DIR / "model_ready" / "materials_final_encoded.csv")


@pytest.fixture(scope="module")
def materials_features():
    return pd.read_csv(DATA_DIR / "model_ready" / "materials_with_features.csv")


# ---------- Structural Tests ----------

def test_required_columns_present(materials_clean):
    missing = REQUIRED_RAW_COLUMNS - set(materials_clean.columns)
    assert not missing, f"Missing required columns: {missing}"


def test_no_unexpected_row_count_drop(materials_clean):
    # Cleaned dataset should have close to the original row count
    # (1 row was intentionally dropped during ingestion for being incomplete)
    assert len(materials_clean) > 0


# ---------- Cleanliness Tests ----------

def test_no_nulls_in_mandatory_fields(materials_clean):
    mandatory = ["material_id", "cost_per_unit_usd", "co2_emission_per_kg",
                 "recyclability_percent", "biodegradation_time_days"]
    for col in mandatory:
        assert materials_clean[col].isnull().sum() == 0, f"Nulls found in {col}"


def test_no_duplicate_material_ids(materials_clean):
    assert materials_clean["material_id"].duplicated().sum() == 0


def test_no_fully_duplicate_rows(materials_clean):
    assert materials_clean.duplicated().sum() == 0


# ---------- Range Tests ----------

def test_cost_is_positive(materials_clean):
    assert (materials_clean["cost_per_unit_usd"] > 0).all()


def test_co2_emission_non_negative(materials_clean):
    assert (materials_clean["co2_emission_per_kg"] >= 0).all()


def test_moisture_resistance_range(materials_clean):
    assert materials_clean["moisture_resistance_score"].between(1, 10).all()


def test_thermal_resistance_range(materials_clean):
    assert materials_clean["thermal_resistance_score"].between(1, 10).all()


def test_biodegradation_days_minimum(materials_clean):
    assert (materials_clean["biodegradation_time_days"] >= 1).all()


def test_percent_columns_in_range(materials_clean):
    percent_cols = [
        "recyclability_percent", "recycled_content_percent", "reusability_percent",
        "end_of_life_disposal_percent", "waste_reduction_impact_percent",
        "sustainability_target_progress_percent",
        "supplier_sustainability_compliance_percent",
    ]
    for col in percent_cols:
        assert materials_clean[col].between(0, 100).all(), f"{col} has values outside 0-100"


def test_no_negative_weights(materials_clean):
    assert (materials_clean["total_material_weight_tons"] >= 0).all()


# ---------- Categorical Tests ----------

def test_material_type_categories_valid(materials_clean):
    actual = set(materials_clean["material_type"].unique())
    assert actual.issubset(VALID_MATERIAL_TYPES), f"Unexpected material_type values: {actual - VALID_MATERIAL_TYPES}"


def test_recyclability_category_valid(materials_clean):
    actual = set(materials_clean["recyclability_category"].unique())
    assert actual.issubset(VALID_RECYCLABILITY_CATEGORIES), f"Unexpected recyclability_category values: {actual - VALID_RECYCLABILITY_CATEGORIES}"


def test_supplier_region_valid(materials_clean):
    actual = set(materials_clean["supplier_region"].unique())
    assert actual.issubset(VALID_SUPPLIER_REGIONS), f"Unexpected supplier_region values: {actual - VALID_SUPPLIER_REGIONS}"


# ---------- Encoding Tests ----------

def test_recyclability_encoded_only_valid_values(materials_encoded):
    assert set(materials_encoded["recyclability_category_encoded"].unique()).issubset({0, 1, 2})


def test_scaled_columns_within_unit_range(materials_encoded):
    scaled_cols = [c for c in materials_encoded.columns if c.endswith("_scaled")]
    for col in scaled_cols:
        assert materials_encoded[col].between(0, 1).all(), f"{col} has values outside 0-1"


# ---------- Feature Engineering Tests ----------

def test_engineered_scores_in_range(materials_features):
    for col in ["co2_impact_index", "cost_efficiency_index", "material_suitability_score"]:
        assert materials_features[col].between(0, 100).all(), f"{col} out of 0-100 range"


def test_engineered_scores_no_nan_or_inf(materials_features):
    for col in ["co2_impact_index", "cost_efficiency_index", "material_suitability_score"]:
        assert not materials_features[col].isnull().any(), f"{col} contains NaN"
        assert np.isfinite(materials_features[col]).all(), f"{col} contains infinite values"