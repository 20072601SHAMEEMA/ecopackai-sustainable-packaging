"""
EcoPackAI - Build Model Metadata
Module: Final Model Packaging

Generates src/inference/metadata.json from the actual artifacts, so the
metadata can never drift from the models it describes: model versions and
metrics come from the experiment records, the feature schema from the fitted
preprocessing pipeline, and file fingerprints (SHA-256) from the files.

Re-run whenever a model is retrained (from the project root):
    python src/inference/build_metadata.py
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
import sklearn
import xgboost
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "src" / "inference" / "metadata.json"
DATA_FILE = "data/processed/materials.csv"

MODELS = {
    "cost": {
        "artifact": "ml/models/rf_cost.joblib",
        "experiment": "RandomForestRegressor__cost_per_unit_usd__v1__*.json",
        "output_column": "predicted_cost_usd",
        "unit": "USD per unit",
        "selection_note": "Lowest test MAE and RMSE of all cost variants (final_model_comparison.csv).",
    },
    "co2": {
        "artifact": "ml/models/xgb_co2.joblib",
        "experiment": "XGBRegressor__co2_emission_per_kg__v1__*.json",
        "output_column": "predicted_co2_per_kg",
        "unit": "kg CO2 per kg of material",
        "selection_note": ("Kept per project architecture. An untuned Random Forest scored slightly "
                           "better (test MAE 0.0350 vs 0.0358); planned as v2. See "
                           "docs/final_model_evaluation.md."),
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def feature_schema(preprocessor, train_df: pd.DataFrame) -> list:
    """Describe every raw input column the pipeline expects."""
    schema = []
    for name, transformer, columns in preprocessor.transformers_:
        if name == "remainder":
            continue
        encoder = transformer.steps[-1][1]
        for i, column in enumerate(columns):
            entry = {"name": column}
            if name == "num":
                entry.update(type="numeric",
                             training_min=float(train_df[column].min()),
                             training_max=float(train_df[column].max()))
            elif name == "nom":
                entry.update(type="categorical", allowed_values=[str(v) for v in encoder.categories_[i]],
                             unknown_values="ignored (all one-hot columns set to 0)")
            else:
                entry.update(type="ordinal", allowed_values=[str(v) for v in encoder.categories_[i]],
                             unknown_values="rejected")
            schema.append(entry)
    return schema


def build() -> dict:
    materials = pd.read_csv(ROOT / DATA_FILE)
    train_df, test_df = train_test_split(materials, test_size=0.2, random_state=42)

    models = {}
    preprocessor = None
    for key, info in MODELS.items():
        records = sorted((ROOT / "ml" / "experiments" / "metadata").glob(info["experiment"]))
        if len(records) != 1:
            raise RuntimeError(f"Expected exactly one experiment record for {key}, found {len(records)}")
        record = json.loads(records[0].read_text(encoding="utf-8"))
        pipeline = joblib.load(ROOT / info["artifact"])
        preprocessor = pipeline.named_steps["preprocess"]

        models[key] = {
            "model_name": record["model_name"],
            "model_version": record["model_version"],
            "experiment_id": record["experiment_id"],
            "training_date": datetime.strptime(record["timestamp"], "%Y%m%d_%H%M%S").isoformat(),
            "target_variable": record["target_variable"],
            "output_column": info["output_column"],
            "unit": info["unit"],
            "artifact_path": info["artifact"],
            "artifact_sha256": sha256(ROOT / info["artifact"]),
            "hyperparameters": {k: v for k, v in record["model_parameters"].items()
                                if v is not None and v == v},   # v == v drops NaN (not valid JSON)
            "metrics": {"cross_validation_5fold": record["cross_validation"], "test_set": record["test_set"]},
            "selection_note": info["selection_note"],
        }

    return {
        "package_name": "ecopackai-material-predictor",
        "package_version": "1.0.0",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "description": "Predicts packaging cost and CO2 per kg for a material from its raw attributes.",
        "library_versions": {"scikit-learn": sklearn.__version__, "xgboost": xgboost.__version__,
                             "pandas": pd.__version__},
        "data": {
            "dataset_version": "v1",
            "feature_set_version": "v1",
            "source_file": DATA_FILE,
            "source_sha256": sha256(ROOT / DATA_FILE),
            "rows": int(len(materials)),
            "split": {"test_size": 0.2, "random_state": 42,
                      "train_rows": int(len(train_df)), "test_rows": int(len(test_df))},
        },
        "input_features": feature_schema(preprocessor, train_df),
        "model_features": [str(n) for n in preprocessor.get_feature_names_out()],
        "targets": {key: m["target_variable"] for key, m in models.items()},
        "models": models,
    }


if __name__ == "__main__":
    metadata = build()
    OUTPUT.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}: {len(metadata['input_features'])} input features, "
          f"{len(metadata['model_features'])} model features, models: {list(metadata['models'])}")
