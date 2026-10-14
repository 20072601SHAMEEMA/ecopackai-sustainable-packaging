"""
EcoPackAI - Prediction Endpoint
Module: Model Serving & API Layer

POST /predict  - validate the request, predict cost and CO2 with the packaged
                 models, return recommendation-ready scores, save every
                 prediction to prediction_history. Needs a client API key.
GET  /schema   - the request/response schema (same content as docs/api_schema.json)

Identical requests are answered from the response cache (header X-Cache: HIT).
The allowed fields, types and category values are read from the packaged
model metadata (src/inference/metadata.json) and the ranking config
(config/ranking_weights.yaml), so the API always matches the models.

Export the schema document (from the project root):
    python backend/routes/predict.py
"""

import hashlib
import json
import sys
import time
import warnings
from functools import lru_cache
from pathlib import Path

import pandas as pd
from flask import Blueprint, current_app, g, jsonify

ROOT = Path(__file__).resolve().parents[2]
for folder in (ROOT / "src", ROOT / "backend"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from cache import make_key  # noqa: E402
from logging_setup import app_log  # noqa: E402
from middleware.auth import require_auth  # noqa: E402
from models import PredictionHistory  # noqa: E402
from recommendation.ranker import (  # noqa: E402
    CRITERIA, filter_candidates, load_config, prepare_materials, suitability_scores,
)
from routes.common import components, error, json_body, model_info  # noqa: E402

METADATA_FILE = ROOT / "src" / "inference" / "metadata.json"
CONFIG_FILE = ROOT / "config" / "ranking_weights.yaml"
SCHEMA_FILE = ROOT / "docs" / "api_schema.json"

SHIPPING_TYPES = ["Air", "Road", "Sea"]          # values in data/processed/products.csv
FRAGILITY_RANGE = (1, 5)

predict_bp = Blueprint("predict", __name__)


# ---------------------------------------------------------------------------
# Field rules (built from metadata.json and the ranking config)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _metadata() -> dict:
    return json.loads(METADATA_FILE.read_text(encoding="utf-8"))


def material_rules() -> dict:
    """name -> rule for every material field the model needs."""
    rules = {}
    for feature in _metadata()["input_features"]:
        name = feature["name"]
        if feature["type"] == "numeric":
            rule = {"type": "number", "minimum": 0}
            if name.endswith("_percent"):
                rule["maximum"] = 100
            elif name.endswith("_score"):
                rule["maximum"] = 10
            rules[name] = rule
        else:
            rules[name] = {"type": "string", "enum": feature["allowed_values"]}
    return rules


def product_rules(config: dict) -> dict:
    return {
        "category": {"type": "string", "enum": sorted(config["category_suitability"])},
        "product_weight_kg": {"type": "number", "exclusiveMinimum": 0},
        "fragility_index": {"type": "integer", "minimum": FRAGILITY_RANGE[0], "maximum": FRAGILITY_RANGE[1]},
        "shipping_type": {"type": "string", "enum": SHIPPING_TYPES},
    }


def _check(value, rule: dict, field: str, errors: list):
    """Validate one value against its rule; append a readable error if it fails."""
    kind = rule["type"]
    if kind == "string":
        if not isinstance(value, str):
            errors.append({"field": field, "message": f"must be text, got {type(value).__name__}"})
        elif "enum" in rule and value not in rule["enum"]:
            errors.append({"field": field, "message": f"'{value}' is not allowed; use one of {rule['enum']}"})
        return
    is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "integer" and not (is_number and float(value).is_integer()):
        errors.append({"field": field, "message": f"must be a whole number, got {value!r}"})
        return
    if not is_number:
        errors.append({"field": field, "message": f"must be a number, got {value!r}"})
        return
    if "minimum" in rule and value < rule["minimum"]:
        errors.append({"field": field, "message": f"must be >= {rule['minimum']}, got {value}"})
    if "exclusiveMinimum" in rule and value <= rule["exclusiveMinimum"]:
        errors.append({"field": field, "message": f"must be > {rule['exclusiveMinimum']}, got {value}"})
    if "maximum" in rule and value > rule["maximum"]:
        errors.append({"field": field, "message": f"must be <= {rule['maximum']}, got {value}"})


def _check_object(obj, rules: dict, prefix: str, errors: list):
    if not isinstance(obj, dict):
        errors.append({"field": prefix, "message": "must be a JSON object"})
        return
    for name, rule in rules.items():
        if obj.get(name) is None:
            errors.append({"field": f"{prefix}.{name}", "message": "is required"})
        else:
            _check(obj[name], rule, f"{prefix}.{name}", errors)


def validate_request(body, config: dict, max_batch: int):
    """Return (materials, product, mode, errors). Collects every error, not just the first."""
    errors = []
    if not isinstance(body, dict):
        return None, None, None, [{"field": "body", "message": "must be a JSON object"}]

    if ("material" in body) == ("materials" in body):
        errors.append({"field": "body", "message": "send exactly one of 'material' (one object) "
                                                   "or 'materials' (a list of objects)"})
        return None, None, None, errors
    materials = [body["material"]] if "material" in body else body["materials"]
    if not isinstance(materials, list) or not materials:
        return None, None, None, [{"field": "materials", "message": "must be a non-empty list"}]
    if len(materials) > max_batch:
        return None, None, None, [{"field": "materials",
                                   "message": f"at most {max_batch} materials per request, got {len(materials)}"}]

    product = body.get("product")
    rules = material_rules()
    for i, material in enumerate(materials):
        prefix = "material" if "material" in body else f"materials[{i}]"
        _check_object(material, rules, prefix, errors)
        if isinstance(material, dict):
            if material.get("material_id") is not None and not isinstance(material["material_id"], str):
                errors.append({"field": f"{prefix}.material_id", "message": "must be text"})
            if product is not None:
                tags = material.get("suitable_product_categories")
                if not isinstance(tags, str) or not tags.strip():
                    errors.append({"field": f"{prefix}.suitable_product_categories",
                                   "message": "is required when 'product' is given "
                                              "(comma-separated list, e.g. 'Electronics, Fragile Items')"})

    if product is not None:
        _check_object(product, product_rules(config), "product", errors)

    options = body.get("options", {})
    mode = config["default_mode"]
    if not isinstance(options, dict):
        errors.append({"field": "options", "message": "must be a JSON object"})
    elif "mode" in options:
        if options["mode"] not in config["modes"]:
            errors.append({"field": "options.mode",
                           "message": f"'{options['mode']}' is not a mode; use one of {list(config['modes'])}"})
        else:
            mode = options["mode"]

    return materials, product, mode, errors


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def compute_predictions(service, materials: list, product, mode: str) -> dict:
    """Predict, score and (with a product) rank the materials. Returns the cacheable payload."""
    frame = pd.DataFrame(materials)
    if "suitable_product_categories" not in frame:
        frame["suitable_product_categories"] = ""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        predicted = service.predictor.predict(frame)
    frame["predicted_cost_usd"] = predicted["predicted_cost_usd"].to_numpy()
    frame["predicted_co2_per_kg"] = predicted["predicted_co2_per_kg"].to_numpy()

    # Scale scores against the whole catalogue, exactly like the ranking engine
    catalogue = service.catalogue[list(frame.columns.intersection(service.catalogue.columns))]
    combined = pd.concat([catalogue, frame], ignore_index=True)
    scored = prepare_materials(combined).tail(len(frame)).reset_index(drop=True)

    ranks = {}
    if product is not None:
        product_series = pd.Series(product)
        weights = service.config["modes"][mode]
        scored["score_suitability"] = suitability_scores(product_series, scored, service.config)
        scored["final_score"] = 100 * sum(weights[c] * scored[f"score_{c}"] for c in CRITERIA)
        eligible = filter_candidates(product_series, scored, service.config)
        order = eligible.assign(_pos=eligible.index).sort_values(
            ["final_score", "_pos"], ascending=[False, True], kind="mergesort")
        ranks = {pos: rank for rank, pos in enumerate(order.index, start=1)}

    results = []
    for i, row in scored.iterrows():
        scores = {c: round(float(row[f"score_{c}"]), 4) for c in ["co2", "cost", "sustainability"]}
        item = {
            "index": i,
            "material_id": materials[i].get("material_id"),
            "predicted_cost_usd": round(float(row["predicted_cost_usd"]), 4),
            "predicted_co2_per_kg": round(float(row["predicted_co2_per_kg"]), 4),
            "scores": scores,
        }
        if product is not None:
            scores["suitability"] = round(float(row["score_suitability"]), 4)
            scores["final_score"] = round(float(row["final_score"]), 4)
            item["eligible"] = i in ranks
            item["rank"] = ranks.get(i)
        results.append(item)

    return {
        "model": model_info(service.predictor.metadata),
        "mode": mode if product is not None else None,
        "product": product,
        "count": len(results),
        "predictions": results,
        "warnings": sorted({str(w.message) for w in caught}),
    }


def save_history(db, materials: list, payload: dict, versions: dict, cached: bool) -> bool:
    """One prediction_history row per material. Returns False (and logs) if the database fails."""
    rows = []
    for material, prediction in zip(materials, payload["predictions"]):
        canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
        rows.append(PredictionHistory(
            request_id=g.request_id, material_id=material.get("material_id"),
            input_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(), inputs=material,
            predicted_cost_usd=prediction["predicted_cost_usd"],
            predicted_co2_per_kg=prediction["predicted_co2_per_kg"],
            cost_model_version=versions["cost"], co2_model_version=versions["co2"], cached=cached))
    try:
        with db.session() as session:
            session.add_all(rows)
        return True
    except Exception:
        app_log.exception("Could not save prediction history", extra={"event": "history_save_failed"})
        return False


@predict_bp.post("/predict")
@require_auth("client")
def predict():
    started = time.perf_counter()
    body, problem = json_body()
    if problem:
        return problem

    parts = components()
    service = parts.service.load()
    key = make_key("/predict", body, service.model_fingerprint, service.config_fingerprint)
    payload = parts.cache.get(key)
    cache_status = "HIT" if payload is not None else "MISS" if parts.cache.enabled else "BYPASS"

    if payload is None:
        materials, product, mode, errors = validate_request(body, service.config,
                                                            current_app.config["MAX_BATCH_SIZE"])
        if errors:
            return error(400, "validation_error", f"{len(errors)} problem(s) in the request.", errors)
        payload = compute_predictions(service, materials, product, mode)
        parts.cache.set(key, payload)
    else:
        materials = [body["material"]] if "material" in body else body["materials"]

    if not save_history(parts.db, materials, payload, service.model_versions(), cache_status == "HIT"):
        payload["warnings"] = payload["warnings"] + ["Prediction could not be saved to prediction_history."]

    app_log.info("Prediction served", extra={
        "event": "prediction", "count": payload["count"], "mode": payload["mode"], "cache": cache_status,
        "with_product": payload["product"] is not None, "warnings": len(payload["warnings"])})
    response = jsonify({"status": "success", "request_id": g.request_id, **payload,
                        "cached": cache_status == "HIT",
                        "processing_ms": round((time.perf_counter() - started) * 1000, 1)})
    response.headers["X-Cache"] = cache_status
    return response


@predict_bp.get("/schema")
def schema():
    return jsonify(build_api_schema())


# ---------------------------------------------------------------------------
# API schema document (docs/api_schema.json)
# ---------------------------------------------------------------------------

def build_api_schema() -> dict:
    """JSON Schema of the /predict and /recommend requests and responses, from the model metadata."""
    config = load_config(CONFIG_FILE)
    material_properties = {
        "material_id": {"type": "string", "description": "Optional; echoed back in the response."},
        "suitable_product_categories": {
            "type": "string",
            "description": "Comma-separated product groups the material suits. Required when 'product' is sent.",
        },
        **material_rules(),
    }
    material = {"type": "object", "required": list(material_rules()), "properties": material_properties}
    product = {"type": "object", "required": list(product_rules(config)),
               "properties": {"product_id": {"type": ["integer", "string"]},
                              "product_name": {"type": "string"},
                              **product_rules(config)}}
    mode = {"type": "string", "enum": list(config["modes"]), "default": config["default_mode"]}
    score = {"type": "number", "minimum": 0, "maximum": 1}
    scores = {"type": "object", "properties": {
        "co2": score, "cost": score, "sustainability": score,
        "suitability": {**score, "description": "Only with a product."},
        "final_score": {"type": "number", "minimum": 0, "maximum": 100, "description": "Only with a product."},
    }}
    common = {
        "status": {"const": "success"},
        "request_id": {"type": "string"},
        "model": {"type": "object", "description": "Model names, versions, targets and units."},
        "cached": {"type": "boolean", "description": "True if served from the response cache."},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "processing_ms": {"type": "number"},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "EcoPackAI API",
        "description": "Generated from src/inference/metadata.json and config/ranking_weights.yaml "
                       "by backend/routes/predict.py. Do not edit by hand.",
        "authentication": "Send a client key as 'X-API-Key: <key>' or 'Authorization: Bearer <key>' "
                          "for /predict and /recommend; /admin/* needs an admin key.",
        "predict_request": {
            "type": "object",
            "description": "Send exactly one of 'material' or 'materials'.",
            "properties": {
                "material": material,
                "materials": {"type": "array", "items": material, "minItems": 1, "maxItems": 100},
                "product": product,
                "options": {"type": "object", "properties": {"mode": mode}},
            },
        },
        "predict_response": {
            "type": "object",
            "properties": {
                **common,
                "mode": {"type": ["string", "null"], "description": "Ranking mode; null without a product."},
                "product": {"type": ["object", "null"]},
                "count": {"type": "integer"},
                "predictions": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "description": "Position in the request."},
                        "material_id": {"type": ["string", "null"]},
                        "predicted_cost_usd": {"type": "number"},
                        "predicted_co2_per_kg": {"type": "number"},
                        "scores": scores,
                        "eligible": {
                            "type": "boolean",
                            "description": "Only with a product: passes all business constraints.",
                        },
                        "rank": {
                            "type": ["integer", "null"],
                            "description": "Only with a product: rank among eligible materials (1 = best).",
                        },
                    },
                }},
            },
        },
        "recommend_request": {
            "type": "object",
            "description": "Send exactly one of 'product_id' (a product in the database) or 'product'.",
            "properties": {
                "product_id": {"type": "integer", "minimum": 1},
                "product": product,
                "options": {"type": "object", "properties": {
                    "mode": mode,
                    "top_n": {"type": "integer", "minimum": 1, "maximum": 20, "default": config["top_n"]},
                }},
            },
        },
        "recommend_response": {
            "type": "object",
            "properties": {
                **common,
                "run_id": {"type": ["integer", "null"], "description": "Row in recommendation_runs."},
                "mode": {"type": "string"},
                "product": {"type": "object"},
                "top_n": {"type": "integer"},
                "n_candidates": {"type": "integer", "description": "Materials that passed the constraints."},
                "result": {"enum": ["ok", "no_valid_material"]},
                "recommendations": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "rank": {"type": "integer"},
                        "material_id": {"type": "string"},
                        "material_type": {"type": "string"},
                        "packaging_type": {"type": "string"},
                        "final_score": {"type": "number", "minimum": 0, "maximum": 100},
                        "predicted_cost_usd": {"type": "number"},
                        "predicted_co2_per_kg": {"type": "number"},
                        "recyclability_percent": {"type": "number"},
                        "scores": scores,
                    },
                }},
            },
        },
        "error_response": {
            "type": "object",
            "properties": {
                "status": {"const": "error"},
                "request_id": {"type": "string"},
                "error": {"type": "object", "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "details": {"type": "array", "items": {"type": "object", "properties": {
                        "field": {"type": "string"}, "message": {"type": "string"}}}},
                }},
            },
        },
    }


if __name__ == "__main__":
    SCHEMA_FILE.write_text(json.dumps(build_api_schema(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {SCHEMA_FILE.relative_to(ROOT)}")
