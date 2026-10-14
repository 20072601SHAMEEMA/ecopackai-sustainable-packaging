"""
EcoPackAI - Unified Prediction Interface
Module: Final Model Packaging

One entry point for cost and CO2 predictions. Loads the packaged models
described in metadata.json, checks that the files are the exact ones the
metadata describes, validates the input against the feature schema, and
predicts for a single material (dict -> dict) or many (DataFrame / list of
dicts -> DataFrame). No retraining happens here.

Usage:
    from inference.predictor import MaterialPredictor

    predictor = MaterialPredictor()
    predictor.predict({"material_type": "Cardboard", ...})      # -> dict
    predictor.predict(materials_df)                              # -> DataFrame
"""

import hashlib
import json
import warnings
from pathlib import Path

import joblib
import pandas as pd
import sklearn
import xgboost

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA = Path(__file__).resolve().parent / "metadata.json"


class MaterialPredictor:
    """Predicts cost per unit (USD) and CO2 per kg for packaging materials."""

    def __init__(self, metadata_path=DEFAULT_METADATA, root=ROOT, verify_files=True):
        self.root = Path(root)
        self.metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
        self._check_library_versions()

        self.models = {}
        for key, info in self.metadata["models"].items():
            path = self.root / info["artifact_path"]
            if verify_files and _sha256(path) != info["artifact_sha256"]:
                raise RuntimeError(f"{path} does not match metadata.json (file changed or retrained). "
                                   "Re-run src/inference/build_metadata.py after retraining.")
            self.models[key] = joblib.load(path)

        self.schema = {f["name"]: f for f in self.metadata["input_features"]}

    @property
    def input_features(self) -> list:
        return list(self.schema)

    @property
    def output_columns(self) -> list:
        return [info["output_column"] for info in self.metadata["models"].values()]

    def validate(self, data: pd.DataFrame) -> pd.DataFrame:
        """Check the input against the feature schema; return only the model's input columns."""
        missing = [c for c in self.schema if c not in data.columns]
        if missing:
            raise ValueError(f"Missing input columns: {missing}")

        frame = data[self.input_features].copy()
        for name, spec in self.schema.items():
            column = frame[name]
            if spec["type"] == "numeric":
                converted = pd.to_numeric(column, errors="coerce")
                bad = column.notna() & converted.isna()
                if bad.any():
                    raise ValueError(f"Column '{name}' must be numeric, got {column[bad].tolist()[:3]}")
                frame[name] = converted
                outside = (converted < spec["training_min"]) | (converted > spec["training_max"])
                if outside.any():
                    warnings.warn(f"{int(outside.sum())} value(s) of '{name}' are outside the training range "
                                  f"[{spec['training_min']}, {spec['training_max']}]; tree models do not "
                                  "extrapolate, so treat these predictions with care.")
            else:
                unknown = column.notna() & ~column.astype(str).isin(spec["allowed_values"])
                if unknown.any() and spec["type"] == "ordinal":
                    raise ValueError(f"Column '{name}' allows {spec['allowed_values']}, "
                                     f"got {sorted(column[unknown].astype(str).unique())}")
                if unknown.any():
                    warnings.warn(f"Unseen value(s) in '{name}': {sorted(column[unknown].astype(str).unique())}; "
                                  "the model treats them as 'none of the known categories'.")

        if frame.isna().any().any():
            warnings.warn("Input has missing values; the pipeline fills them with training medians/modes.")
        return frame

    def predict(self, data):
        """Predict for one material (dict -> dict) or many (DataFrame / list of dicts -> DataFrame)."""
        single = isinstance(data, dict)
        if single:
            frame = pd.DataFrame([data])
        elif isinstance(data, list):
            frame = pd.DataFrame(data)
        elif isinstance(data, pd.DataFrame):
            frame = data
        else:
            raise TypeError("predict() expects a dict, a list of dicts or a pandas DataFrame")
        if frame.empty:
            raise ValueError("No rows to predict")

        features = self.validate(frame)
        result = pd.DataFrame(index=frame.index)
        if "material_id" in frame.columns:
            result["material_id"] = frame["material_id"]
        for key, info in self.metadata["models"].items():
            result[info["output_column"]] = self.models[key].predict(features)

        if single:
            return {k: (float(v) if k != "material_id" else v) for k, v in result.iloc[0].items()}
        return result

    def info(self) -> dict:
        """Short summary of the packaged models (for logs or an API /health endpoint)."""
        return {key: {"model": m["model_name"], "version": m["model_version"],
                      "target": m["target_variable"], "test_metrics": m["metrics"]["test_set"]}
                for key, m in self.metadata["models"].items()}

    def _check_library_versions(self):
        installed = {"scikit-learn": sklearn.__version__, "xgboost": xgboost.__version__}
        for library, version in installed.items():
            expected = self.metadata["library_versions"][library]
            if version != expected:
                warnings.warn(f"{library} {version} is installed but the models were saved with {expected}; "
                              "predictions may differ. Install the versions in environments/requirements.txt.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
