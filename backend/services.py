"""
EcoPackAI - Model Service
Module: Flask Backend

One PredictionService per app. It is loaded lazily (on the first /predict or
/recommend request, never by /health) and only once:
    - the packaged predictor (src/inference/predictor.py)
    - the ranking config (config/ranking_weights.yaml)
    - the material catalogue with predictions, read from the materials table
      (falls back to data/processed/materials.csv if the table is empty)
    - fingerprints of the models and config, used in cache keys
"""

import hashlib
import json
import sys
import threading
import warnings
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from inference.predictor import MaterialPredictor  # noqa: E402
from logging_setup import app_log  # noqa: E402
from models import Material  # noqa: E402
from recommendation.ranker import load_config, prepare_materials  # noqa: E402

CONFIG_FILE = ROOT / "config" / "ranking_weights.yaml"
CATALOGUE_CSV = ROOT / "data" / "processed" / "materials.csv"


class PredictionService:
    def __init__(self, db):
        self.db = db
        self._lock = threading.Lock()
        self.predictor = None
        self.config = None
        self.catalogue = None           # materials + predictions + ranking scores
        self.catalogue_source = None
        self.model_fingerprint = None
        self.config_fingerprint = None

    @property
    def is_loaded(self) -> bool:
        return self.predictor is not None

    def load(self) -> "PredictionService":
        with self._lock:
            if self.is_loaded:
                return self
            config = load_config(CONFIG_FILE)
            predictor = MaterialPredictor()
            materials, source = self._read_catalogue()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                predictions = predictor.predict(materials)
            materials["predicted_cost_usd"] = predictions["predicted_cost_usd"].to_numpy()
            materials["predicted_co2_per_kg"] = predictions["predicted_co2_per_kg"].to_numpy()

            self.config = config
            self.catalogue = prepare_materials(materials)
            self.catalogue_source = source
            self.model_fingerprint = hashlib.sha256("".join(
                m["artifact_sha256"] for m in predictor.metadata["models"].values()).encode()).hexdigest()[:16]
            self.config_fingerprint = hashlib.sha256(
                json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()[:16]
            self.predictor = predictor              # set last: marks the service as loaded
            app_log.info("Models loaded", extra={"event": "models_loaded", "catalogue_source": source,
                                                 "catalogue_size": len(materials)})
            return self

    def _read_catalogue(self):
        columns = [c.name for c in Material.__table__.columns]
        try:
            with self.db.engine.connect() as connection:
                frame = pd.read_sql_table(Material.__tablename__, connection)
            # SQLAlchemy returns column names as 'quoted_name' objects; scikit-learn only
            # accepts plain str feature names, so convert them.
            frame.columns = [f"{name}" for name in frame.columns]
            if len(frame):
                return frame[columns].sort_values("material_id").reset_index(drop=True), "database"
        except Exception:                           # database unreachable or not migrated yet
            app_log.exception("Could not read materials from the database; using the CSV")
        frame = pd.read_csv(CATALOGUE_CSV)
        app_log.warning("Materials table is empty; run 'python backend/manage.py init-db'",
                        extra={"event": "catalogue_fallback"})
        return frame[columns], "csv"

    def model_versions(self) -> dict:
        models = self.predictor.metadata["models"]
        return {key: f"{m['model_name']} v{m['model_version']}" for key, m in models.items()}
