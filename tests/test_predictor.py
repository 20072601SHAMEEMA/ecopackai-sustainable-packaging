"""
EcoPackAI - Packaged Predictor Tests
Module: Final Model Packaging

Checks that the packaged models load without retraining, give the same
predictions as the original pipelines, accept single and batch input,
reject bad input clearly, and that metadata.json matches the artifacts.

Run with: pytest tests/test_predictor.py -v
"""

import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Random Forest averages its trees in parallel threads, so the last digits
# (~1e-14) can differ between calls; anything below 1e-9 counts as identical.
SAME = {"rtol": 0, "atol": 1e-9}

from inference.predictor import MaterialPredictor  # noqa: E402
from recommendation.ranker import add_predictions  # noqa: E402


@pytest.fixture(scope="module")
def predictor():
    with warnings.catch_warnings():
        warnings.simplefilter("error")          # wrong library versions would fail here
        return MaterialPredictor()


@pytest.fixture(scope="module")
def materials():
    return pd.read_csv(ROOT / "data" / "processed" / "materials.csv")


@pytest.fixture(scope="module")
def test_df(materials):
    return train_test_split(materials, test_size=0.2, random_state=42)[1]


# ---- Loading and consistency ----

def test_models_load_without_retraining(predictor):
    assert set(predictor.models) == {"cost", "co2"}
    assert predictor.output_columns == ["predicted_cost_usd", "predicted_co2_per_kg"]


def test_predictions_match_original_pipelines(predictor, test_df):
    result = predictor.predict(test_df)
    rf = joblib.load(ROOT / "ml" / "models" / "rf_cost.joblib")
    xgb = joblib.load(ROOT / "ml" / "models" / "xgb_co2.joblib")
    assert np.allclose(result["predicted_cost_usd"], rf.predict(test_df), **SAME)
    assert np.allclose(result["predicted_co2_per_kg"], xgb.predict(test_df), **SAME)


def test_test_set_metrics_match_metadata(predictor, test_df):
    result = predictor.predict(test_df)
    for key, info in predictor.metadata["models"].items():
        mae = mean_absolute_error(test_df[info["target_variable"]], result[info["output_column"]])
        assert mae == pytest.approx(info["metrics"]["test_set"]["mae"], abs=1e-6)


# ---- Single and batch input ----

def test_single_dict_returns_dict(predictor, materials):
    row = materials.iloc[0].to_dict()
    result = predictor.predict(row)
    assert isinstance(result, dict)
    assert result["material_id"] == row["material_id"]
    assert result["predicted_cost_usd"] > 0 and result["predicted_co2_per_kg"] > 0


def test_single_and_batch_agree(predictor, materials):
    batch = predictor.predict(materials.head(5))
    single = predictor.predict(materials.iloc[2].to_dict())
    assert single["predicted_cost_usd"] == pytest.approx(batch.iloc[2]["predicted_cost_usd"])
    assert single["predicted_co2_per_kg"] == pytest.approx(batch.iloc[2]["predicted_co2_per_kg"])


def test_list_of_dicts_returns_dataframe(predictor, materials):
    result = predictor.predict(materials.head(3).to_dict("records"))
    assert isinstance(result, pd.DataFrame) and len(result) == 3


def test_extra_columns_are_ignored(predictor, materials):
    rows = materials.head(3).assign(some_note="ignored")
    assert len(predictor.predict(rows)) == 3


# ---- Input validation ----

def test_missing_column_is_rejected(predictor, materials):
    with pytest.raises(ValueError, match="Missing input columns"):
        predictor.predict(materials.head(2).drop(columns=["reusability_percent"]))


def test_non_numeric_value_is_rejected(predictor, materials):
    row = materials.iloc[0].to_dict()
    row["load_handling_score"] = "strong"
    with pytest.raises(ValueError, match="must be numeric"):
        predictor.predict(row)


def test_unknown_ordinal_value_is_rejected(predictor, materials):
    row = materials.iloc[0].to_dict()
    row["recyclability_category"] = "Very High"
    with pytest.raises(ValueError, match="recyclability_category"):
        predictor.predict(row)


def test_unseen_category_warns_but_predicts(predictor, materials):
    row = materials.iloc[0].to_dict()
    row["supplier_region"] = "ANTARCTICA"
    with pytest.warns(UserWarning, match="Unseen value"):
        result = predictor.predict(row)
    assert result["predicted_cost_usd"] > 0


def test_out_of_range_value_warns(predictor, materials):
    row = materials.iloc[0].to_dict()
    row["total_material_weight_tons"] = 1e6
    with pytest.warns(UserWarning, match="outside the training range"):
        predictor.predict(row)


def test_wrong_input_type_is_rejected(predictor):
    with pytest.raises(TypeError):
        predictor.predict("Cardboard")


# ---- Metadata ----

def test_metadata_has_required_fields(predictor):
    meta = predictor.metadata
    for key in ["library_versions", "data", "input_features", "model_features", "targets", "models"]:
        assert key in meta
    for model in meta["models"].values():
        for key in ["model_name", "model_version", "training_date", "target_variable",
                    "metrics", "artifact_path", "artifact_sha256"]:
            assert key in model


def test_metadata_feature_schema_matches_pipeline(predictor):
    pipeline = predictor.models["cost"].named_steps["preprocess"]
    assert predictor.metadata["model_features"] == list(pipeline.get_feature_names_out())
    assert len(predictor.input_features) == 18


def test_changed_model_file_is_detected(tmp_path):
    meta = json.loads((ROOT / "src" / "inference" / "metadata.json").read_text(encoding="utf-8"))
    meta["models"]["cost"]["artifact_sha256"] = "0" * 64
    fake = tmp_path / "metadata.json"
    fake.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(RuntimeError, match="does not match metadata"):
        MaterialPredictor(metadata_path=fake)


# ---- Recommendation pipeline integration ----

def test_ranker_uses_predictor(predictor, materials):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        enriched = add_predictions(materials, predictor)
    direct = predictor.predict(materials)
    assert np.allclose(enriched["predicted_cost_usd"], direct["predicted_cost_usd"], **SAME)
    assert np.allclose(enriched["predicted_co2_per_kg"], direct["predicted_co2_per_kg"], **SAME)
