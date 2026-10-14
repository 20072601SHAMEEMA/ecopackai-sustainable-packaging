"""
EcoPackAI - Recommendation Endpoint
Module: Flask Backend

POST /recommend - rank the whole material catalogue for one product and
                  return the top N, using src/recommendation/ranker.py.
                  Every call is saved: one recommendation_runs row plus one
                  recommendation_logs row per recommended material.
                  Needs a client API key. Identical requests are cached.

Request: exactly one of
    {"product_id": 7}                                    a product in the database
    {"product": {"category": "Food", ...}}               a product sent inline
plus optional "options": {"mode": "balanced", "top_n": 5}
"""

import time

import pandas as pd
from flask import Blueprint, current_app, g, jsonify

from cache import make_key
from logging_setup import app_log
from middleware.auth import require_auth
from models import Product, RecommendationLog, RecommendationRun
from recommendation.ranker import rank_for_product
from routes.common import components, error, json_body, model_info
from routes.predict import _check_object, product_rules

recommend_bp = Blueprint("recommend", __name__)


def validate_recommend(body, config: dict, max_top_n: int):
    """Return (product_id, inline_product, mode, top_n, errors)."""
    if not isinstance(body, dict):
        return None, None, None, None, [{"field": "body", "message": "must be a JSON object"}]
    errors = []
    if ("product_id" in body) == ("product" in body):
        return None, None, None, None, [{"field": "body", "message": "send exactly one of 'product_id' "
                                                                     "or 'product'"}]
    product_id = body.get("product_id")
    if "product_id" in body and (not isinstance(product_id, int) or isinstance(product_id, bool)
                                 or product_id < 1):
        errors.append({"field": "product_id", "message": f"must be a positive whole number, got {product_id!r}"})
    inline = body.get("product")
    if "product" in body:
        _check_object(inline, product_rules(config), "product", errors)

    options = body.get("options", {})
    mode, top_n = config["default_mode"], config["top_n"]
    if not isinstance(options, dict):
        errors.append({"field": "options", "message": "must be a JSON object"})
    else:
        if "mode" in options:
            if options["mode"] in config["modes"]:
                mode = options["mode"]
            else:
                errors.append({"field": "options.mode", "message": f"'{options['mode']}' is not a mode; "
                                                                   f"use one of {list(config['modes'])}"})
        if "top_n" in options:
            value = options["top_n"]
            if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= max_top_n:
                top_n = value
            else:
                errors.append({"field": "options.top_n",
                               "message": f"must be a whole number from 1 to {max_top_n}, got {value!r}"})
    return product_id, inline, mode, top_n, errors


def rank(service, product: dict, mode: str, top_n: int) -> dict:
    """Rank the catalogue for the product; return the cacheable payload."""
    ranked = rank_for_product(pd.Series({"product_id": None, "product_name": None, **product}), service.catalogue,
                              service.config, mode, top_n)
    ok = ranked["status"].iloc[0] == "ok"
    recommendations = []
    if ok:
        for _, row in ranked.iterrows():
            recommendations.append({
                "rank": int(row["rank"]),
                "material_id": row["material_id"],
                "material_type": row["material_type"],
                "packaging_type": row["packaging_type"],
                "final_score": round(float(row["final_score"]), 4),
                "predicted_cost_usd": round(float(row["predicted_cost_usd"]), 4),
                "predicted_co2_per_kg": round(float(row["predicted_co2_per_kg"]), 4),
                "recyclability_percent": float(row["recyclability_percent"]),
                "scores": {c: round(float(row[f"score_{c}"]), 4)
                           for c in ["co2", "cost", "suitability", "sustainability"]},
            })
    return {
        "model": model_info(service.predictor.metadata),
        "mode": mode,
        "product": product,
        "top_n": top_n,
        "n_candidates": int(ranked["n_candidates"].iloc[0]),
        "result": "ok" if ok else "no_valid_material",
        "recommendations": recommendations,
        "warnings": [] if ok else ["No material in the catalogue meets all constraints for this product."],
    }


def save_run(db, payload: dict, db_product_id, versions: dict, cached: bool):
    """Store the run and its ranked materials; return the run_id (None if the database fails)."""
    try:
        with db.session() as session:
            run = RecommendationRun(
                request_id=g.request_id, product_id=db_product_id, product_snapshot=payload["product"],
                mode=payload["mode"], top_n=payload["top_n"], n_candidates=payload["n_candidates"],
                status=payload["result"], cost_model_version=versions["cost"],
                co2_model_version=versions["co2"], cached=cached)
            run.results = [RecommendationLog(
                product_id=db_product_id, recommended_material_id=item["material_id"],
                cost_prediction=item["predicted_cost_usd"], co2_prediction=item["predicted_co2_per_kg"],
                final_score=item["final_score"], material_rank=item["rank"])
                for item in payload["recommendations"]]
            session.add(run)
            session.flush()
            return run.run_id
    except Exception:
        app_log.exception("Could not save recommendation run", extra={"event": "run_save_failed"})
        return None


@recommend_bp.post("/recommend")
@require_auth("client")
def recommend():
    started = time.perf_counter()
    body, problem = json_body()
    if problem:
        return problem

    parts = components()
    service = parts.service.load()
    key = make_key("/recommend", body, service.model_fingerprint, service.config_fingerprint)
    payload = parts.cache.get(key)
    cache_status = "HIT" if payload is not None else "MISS" if parts.cache.enabled else "BYPASS"
    db_product_id = body.get("product_id") if isinstance(body, dict) else None

    if payload is None:
        product_id, inline, mode, top_n, errors = validate_recommend(body, service.config,
                                                                     current_app.config["MAX_TOP_N"])
        if errors:
            return error(400, "validation_error", f"{len(errors)} problem(s) in the request.", errors)
        if product_id is not None:
            try:
                with parts.db.session() as session:
                    found = session.get(Product, product_id)
                    product = found.as_ranking_input() if found else None
            except Exception:
                app_log.exception("Product lookup failed", extra={"event": "db_error"})
                return error(503, "database_unavailable", "The database is not reachable.")
            if product is None:
                return error(404, "not_found", f"No product with product_id {product_id}.")
        else:
            product = dict(inline)
            db_product_id = None                     # inline products are not linked to the table
        payload = rank(service, product, mode, top_n)
        parts.cache.set(key, payload)

    run_id = save_run(parts.db, payload, db_product_id, service.model_versions(), cache_status == "HIT")
    if run_id is None:
        payload["warnings"] = payload["warnings"] + ["Recommendation could not be saved to the database."]

    app_log.info("Recommendation served", extra={
        "event": "recommendation", "product_id": db_product_id, "mode": payload["mode"],
        "result": payload["result"], "n_candidates": payload["n_candidates"], "cache": cache_status,
        "run_id": run_id})
    response = jsonify({"status": "success", "request_id": g.request_id, "run_id": run_id, **payload,
                        "cached": cache_status == "HIT",
                        "processing_ms": round((time.perf_counter() - started) * 1000, 1)})
    response.headers["X-Cache"] = cache_status
    return response
