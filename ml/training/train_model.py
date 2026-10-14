"""
EcoPackAI - Standardized Training Workflow
Module: Experiment Tracking & Model Versioning

Reusable function to train a model, evaluate it, save the versioned
artifact, and log a structured experiment metadata record. Use this
same function for every model trained in this project (baselines,
Random Forest, XGBoost) so every experiment is logged consistently.

Usage (as a library):
    from train_model import run_experiment

    run_experiment(
        model=LinearRegression(),
        model_name="LinearRegression",
        target_name="cost_per_unit_usd",
        X_train=X_train_transformed, y_train=y_cost_train,
        X_test=X_test_transformed, y_test=y_cost_test,
        dataset_version="v1",
        feature_set_version="v1",
        notes="Baseline model, default hyperparameters."
    )
"""

import os
import json
import joblib
from datetime import datetime
from pathlib import Path

from sklearn.model_selection import cross_validate
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score

MODELS_DIR = Path("ml/models")
EXPERIMENTS_DIR = Path("ml/experiments")
METADATA_DIR = EXPERIMENTS_DIR / "metadata"


def _next_version(model_name: str, target_name: str) -> int:
    """Scan existing metadata files to find the next version number
    for this model+target combination, so re-running never silently
    overwrites a previous experiment's artifact."""
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"{model_name}__{target_name}__v"
    existing_versions = []
    for f in METADATA_DIR.glob(f"{prefix}*"):
        try:
            version_part = f.name.split("__v")[1].split("__")[0]
            existing_versions.append(int(version_part))
        except (IndexError, ValueError):
            continue
    return max(existing_versions, default=0) + 1


def run_experiment(
    model,
    model_name: str,
    target_name: str,
    X_train, y_train,
    X_test, y_test,
    dataset_version: str = "v1",
    feature_set_version: str = "v1",
    cv_folds: int = 5,
    notes: str = "",
):
    """
    Trains `model` on (X_train, y_train), evaluates with cross-validation
    and on the held-out test set, saves a versioned model artifact, and
    writes a metadata JSON recording the full experiment configuration
    and results.

    Returns the version number assigned to this run.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    version = _next_version(model_name, target_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_id = f"{model_name}__{target_name}__v{version}__{timestamp}"

    # Cross-validation on training data only
    cv_results = cross_validate(
        model, X_train, y_train,
        cv=cv_folds,
        scoring=["neg_mean_absolute_error", "neg_root_mean_squared_error", "r2"],
    )
    cv_mae = float((-cv_results["test_neg_mean_absolute_error"]).mean())
    cv_rmse = float((-cv_results["test_neg_root_mean_squared_error"]).mean())
    cv_r2 = float(cv_results["test_r2"].mean())

    # Fit on full training data, evaluate on held-out test set
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    test_mae = float(mean_absolute_error(y_test, preds))
    test_rmse = float(root_mean_squared_error(y_test, preds))
    test_r2 = float(r2_score(y_test, preds))

    # Save versioned model artifact
    model_filename = f"{model_name}_{target_name}_v{version}.pkl"
    model_path = MODELS_DIR / model_filename
    joblib.dump(model, model_path)

    # Build and save metadata record
    metadata = {
        "experiment_id": experiment_id,
        "timestamp": timestamp,
        "model_name": model_name,
        "target_variable": target_name,
        "model_version": version,
        "dataset_version": dataset_version,
        "feature_set_version": feature_set_version,
        "model_parameters": model.get_params(),
        "cross_validation": {
            "folds": cv_folds,
            "mean_mae": cv_mae,
            "mean_rmse": cv_rmse,
            "mean_r2": cv_r2,
        },
        "test_set": {
            "mae": test_mae,
            "rmse": test_rmse,
            "r2": test_r2,
        },
        "model_artifact_path": str(model_path),
        "notes": notes,
    }

    metadata_path = METADATA_DIR / f"{experiment_id}.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Experiment logged: {experiment_id}")
    print(f"  Model saved to: {model_path}")
    print(f"  Metadata saved to: {metadata_path}")
    print(f"  Test R2: {test_r2:.4f}, Test MAE: {test_mae:.4f}, Test RMSE: {test_rmse:.4f}")

    return version
