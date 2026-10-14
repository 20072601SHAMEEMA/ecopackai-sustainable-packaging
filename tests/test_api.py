"""
EcoPackAI - API Tests (unit + integration)
Module: Flask Backend - Quality Assurance

Endpoints: /health, /ready, /predict, /recommend, /schema, /admin/*
Covers: input validation, prediction logic, error handling, authentication
and authorisation, caching, database persistence, logging, response
schema and HTTP status codes. Uses Flask's test client (no server needed)
and the database prepared in conftest.py.

Run with: pytest tests/test_api.py -v
"""

import json
import time

import pandas as pd
import pytest
from conftest import ADMIN, ADMIN_KEY, CLIENT, CLIENT_KEY, MATERIALS, PRODUCT, ROOT, material
from sqlalchemy import func, select

from models import PredictionHistory, RecommendationRun
from recommendation.ranker import add_predictions, load_config, prepare_materials, rank_for_product
from routes.predict import build_api_schema

PREDICT_KEYS = {"status", "request_id", "model", "mode", "product", "count", "predictions", "warnings",
                "cached", "processing_ms"}
RECOMMEND_KEYS = {"status", "request_id", "run_id", "model", "mode", "product", "top_n", "n_candidates",
                  "result", "recommendations", "warnings", "cached", "processing_ms"}


def post(client, path, body, headers=CLIENT, **kwargs):
    return client.post(path, json=body, headers=headers, **kwargs)


def details(response):
    assert response.status_code == 400
    body = response.get_json()
    assert body["status"] == "error" and body["error"]["code"] == "validation_error"
    return {d["field"]: d["message"] for d in body["error"]["details"]}


# =========================================================================
# Health and readiness
# =========================================================================

def test_health_is_fast_open_and_loads_nothing(make_app):
    fresh = make_app()
    started = time.perf_counter()
    response = fresh.test_client().get("/health")            # no API key
    elapsed_ms = (time.perf_counter() - started) * 1000
    body = response.get_json()
    assert response.status_code == 200 and body["status"] == "ok"
    assert body["models_loaded"] is False
    assert fresh.extensions["ecopackai"].service.is_loaded is False
    assert elapsed_ms < 100


def test_ready_checks_database_schema_and_data(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ready",
                                   "checks": {"database": "ok", "schema": "ok", "materials": "ok"}}


def test_ready_reports_unreachable_database(make_app, tmp_path):
    broken = make_app(DATABASE_URL=f"sqlite:///{(tmp_path / 'missing' / 'x.db').as_posix()}?mode=ro&uri=true")
    response = broken.test_client().get("/ready")
    assert response.status_code == 503 and response.get_json()["status"] == "not_ready"


# =========================================================================
# /predict - valid requests
# =========================================================================

def test_single_material_prediction(client):
    response = post(client, "/predict", {"material": material(0)})
    body = response.get_json()
    assert response.status_code == 200 and set(body) == PREDICT_KEYS
    item = body["predictions"][0]
    assert item["material_id"] == "MAT_0001"
    assert item["predicted_cost_usd"] > 0 and item["predicted_co2_per_kg"] > 0
    assert set(item["scores"]) == {"co2", "cost", "sustainability"}
    assert body["model"]["cost"]["name"] == "RandomForestRegressor"
    assert body["model"]["co2"]["name"] == "XGBRegressor"


def test_batch_prediction_matches_predictor(client, app):
    body = post(client, "/predict", {"materials": [material(i) for i in range(5)]}).get_json()
    direct = app.extensions["ecopackai"].service.predictor.predict(MATERIALS.head(5))
    assert [p["material_id"] for p in body["predictions"]] == list(MATERIALS["material_id"].head(5))
    for item, (_, row) in zip(body["predictions"], direct.iterrows()):
        assert item["predicted_cost_usd"] == pytest.approx(row["predicted_cost_usd"], abs=1e-4)
        assert item["predicted_co2_per_kg"] == pytest.approx(row["predicted_co2_per_kg"], abs=1e-4)


def test_response_format_is_consistent(client):
    single = post(client, "/predict", {"material": material(1)}).get_json()
    batch = post(client, "/predict", {"materials": [material(1), material(2)]}).get_json()
    with_product = post(client, "/predict", {"materials": [material(1)], "product": PRODUCT}).get_json()
    assert set(single) == set(batch) == set(with_product) == PREDICT_KEYS
    assert single["predictions"][0]["predicted_cost_usd"] == batch["predictions"][0]["predicted_cost_usd"]


def test_product_adds_ranking_scores(client):
    body = post(client, "/predict", {"materials": [material(i) for i in range(10)], "product": PRODUCT,
                                     "options": {"mode": "cost_first"}}).get_json()
    assert body["mode"] == "cost_first"
    ranked = sorted((p for p in body["predictions"] if p["eligible"]), key=lambda p: p["rank"])
    assert [p["rank"] for p in ranked] == list(range(1, len(ranked) + 1))
    scores = [p["scores"]["final_score"] for p in ranked]
    assert scores == sorted(scores, reverse=True)
    assert all(p["rank"] is None for p in body["predictions"] if not p["eligible"])


def test_predict_scores_match_the_ranking_engine(client, app):
    config = load_config(ROOT / "config" / "ranking_weights.yaml")
    catalogue = prepare_materials(add_predictions(MATERIALS, app.extensions["ecopackai"].service.predictor))
    expected = rank_for_product(pd.Series({**PRODUCT, "product_name": "Test"}), catalogue, config, "balanced", 5)
    rows = [material(int(MATERIALS.index[MATERIALS["material_id"] == m][0])) for m in expected["material_id"]]
    body = post(client, "/predict", {"materials": rows, "product": PRODUCT}).get_json()
    for item, (_, row) in zip(body["predictions"], expected.iterrows()):
        assert item["material_id"] == row["material_id"]
        assert item["scores"]["final_score"] == pytest.approx(row["final_score"], abs=1e-3)
        assert item["rank"] == row["rank"]


def test_out_of_range_value_gives_warning_not_error(client):
    body = post(client, "/predict", {"material": material(0, total_material_weight_tons=1e6)}).get_json()
    assert body["status"] == "success"
    assert any("outside the training range" in w for w in body["warnings"])


# =========================================================================
# /predict - invalid requests and error handling
# =========================================================================

def test_missing_field_is_reported(client):
    row = material(0)
    del row["reusability_percent"]
    assert details(post(client, "/predict", {"material": row})) == {"material.reusability_percent": "is required"}


def test_wrong_type_is_reported(client):
    errors = details(post(client, "/predict", {"material": material(0, load_handling_score="strong")}))
    assert "must be a number" in errors["material.load_handling_score"]


def test_invalid_category_is_reported(client):
    errors = details(post(client, "/predict", {"material": material(0, material_type="Glass")}))
    assert "not allowed" in errors["material.material_type"]


def test_out_of_bounds_number_is_reported(client):
    errors = details(post(client, "/predict", {"material": material(0, recyclability_percent=140)}))
    assert "<= 100" in errors["material.recyclability_percent"]


def test_all_errors_reported_at_once(client):
    rows = [material(0, material_type="Glass"), material(1, recyclability_percent=-5)]
    assert set(details(post(client, "/predict", {"materials": rows}))) == \
        {"materials[0].material_type", "materials[1].recyclability_percent"}


def test_invalid_product_is_reported(client):
    product = {**PRODUCT, "category": "Toys", "fragility_index": 9, "shipping_type": "Rail"}
    errors = details(post(client, "/predict", {"material": material(0), "product": product}))
    assert set(errors) == {"product.category", "product.fragility_index", "product.shipping_type"}


def test_product_requires_material_categories(client):
    errors = details(post(client, "/predict", {"material": material(0, suitable_product_categories=None),
                                               "product": PRODUCT}))
    assert "material.suitable_product_categories" in errors


def test_unknown_mode_is_reported(client):
    errors = details(post(client, "/predict", {"material": material(0), "product": PRODUCT,
                                               "options": {"mode": "fastest"}}))
    assert "options.mode" in errors


@pytest.mark.parametrize("body", [{}, {"material": material(0), "materials": [material(1)]},
                                  {"materials": []}, {"materials": "MAT_0001"}, [1, 2]])
def test_malformed_body_is_rejected(client, body):
    assert post(client, "/predict", body).status_code == 400


def test_batch_limit_is_enforced(client):
    response = post(client, "/predict", {"materials": [material(0)] * 101})
    assert response.status_code == 400 and "at most 100" in json.dumps(response.get_json())


def test_non_json_is_rejected(client):
    response = client.post("/predict", data="material_type=Cardboard", headers=CLIENT)
    assert response.status_code == 415 and response.get_json()["status"] == "error"


def test_broken_json_is_rejected(client):
    response = client.post("/predict", data="{not json", content_type="application/json", headers=CLIENT)
    assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_json"


def test_oversized_body_is_rejected(client):
    response = client.post("/predict", data="x" * (2 * 1024 * 1024), content_type="application/json",
                           headers=CLIENT)
    assert response.status_code == 413


def test_unknown_route_returns_json_404(client):
    response = client.get("/nope")
    assert response.status_code == 404 and response.get_json()["status"] == "error"


def test_wrong_method_returns_json_405(client):
    assert client.get("/predict").status_code == 405


def test_unexpected_error_hides_details(make_app, monkeypatch):
    broken = make_app()
    service = broken.extensions["ecopackai"].service
    monkeypatch.setattr(service, "load", lambda: (_ for _ in ()).throw(RuntimeError("secret internal detail")))
    response = post(broken.test_client(), "/predict", {"material": material(0)})
    assert response.status_code == 500
    assert response.get_json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in response.get_data(as_text=True)


# =========================================================================
# /recommend
# =========================================================================

def test_recommend_for_database_product(client):
    response = post(client, "/recommend", {"product_id": 1, "options": {"top_n": 3}})
    body = response.get_json()
    assert response.status_code == 200 and set(body) == RECOMMEND_KEYS
    assert body["product"]["product_name"] == "Chocolate Box" and body["result"] == "ok"
    assert [r["rank"] for r in body["recommendations"]] == [1, 2, 3]
    scores = [r["final_score"] for r in body["recommendations"]]
    assert scores == sorted(scores, reverse=True)


def test_recommend_matches_saved_rankings(client):
    """Same products, same scores as outputs/material_rankings.csv (built by the ranker CLI)."""
    saved = pd.read_csv(ROOT / "outputs" / "material_rankings.csv")
    for product_id in (1, 2, 92):
        expected = saved[(saved["product_id"] == product_id) & (saved["mode"] == "cost_first")]
        body = post(client, "/recommend", {"product_id": product_id, "options": {"mode": "cost_first"}}).get_json()
        assert [r["material_id"] for r in body["recommendations"]] == list(expected["material_id"])
        for item, score in zip(body["recommendations"], expected["final_score"]):
            assert item["final_score"] == pytest.approx(score, abs=1e-3)


def test_recommend_inline_product(client):
    body = post(client, "/recommend", {"product": {"category": "Electronics", "product_weight_kg": 0.3,
                                                   "fragility_index": 5, "shipping_type": "Air"}}).get_json()
    assert body["result"] == "ok"
    assert all(r["packaging_type"] in {"Protective Fillers (Paper/Biodegradable)",
                                       "Foldable & Stackable Containers"} for r in body["recommendations"])


def test_recommend_no_valid_material(client):
    body = post(client, "/recommend", {"product_id": 775}).get_json()      # fragile wine bottle by sea
    assert body["result"] == "no_valid_material" and body["recommendations"] == []
    assert body["n_candidates"] == 0 and body["warnings"]


def test_recommend_unknown_product_is_404(client):
    response = post(client, "/recommend", {"product_id": 999999})
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("body, field", [
    ({}, "body"),
    ({"product_id": 1, "product": PRODUCT}, "body"),
    ({"product_id": "one"}, "product_id"),
    ({"product_id": 1, "options": {"top_n": 50}}, "options.top_n"),
    ({"product_id": 1, "options": {"mode": "fastest"}}, "options.mode"),
    ({"product": {**PRODUCT, "shipping_type": "Rail"}}, "product.shipping_type"),
])
def test_recommend_validation(client, body, field):
    assert field in details(post(client, "/recommend", body))


# =========================================================================
# Database persistence (integration)
# =========================================================================

def _count(db, model, **where):
    with db.session() as session:
        query = select(func.count()).select_from(model)
        for column, value in where.items():
            query = query.where(getattr(model, column) == value)
        return session.scalar(query)


def test_predictions_are_saved(client, db):
    response = post(client, "/predict", {"materials": [material(3), material(4)]},
                    headers={**CLIENT, "X-Request-ID": "save-check-0001"})
    assert response.status_code == 200
    with db.session() as session:
        rows = session.scalars(select(PredictionHistory).where(
            PredictionHistory.request_id == "save-check-0001").order_by(PredictionHistory.id)).all()
    assert [r.material_id for r in rows] == ["MAT_0004", "MAT_0005"]
    first = response.get_json()["predictions"][0]
    assert rows[0].predicted_cost_usd == pytest.approx(first["predicted_cost_usd"])
    assert rows[0].inputs["material_type"] == material(3)["material_type"]
    assert rows[0].cost_model_version == "RandomForestRegressor v1"
    assert len(rows[0].input_hash) == 64


def test_recommendations_are_saved_and_linked(client, db):
    body = post(client, "/recommend", {"product_id": 2, "options": {"top_n": 4}},
                headers={**CLIENT, "X-Request-ID": "run-check-0001"}).get_json()
    with db.session() as session:
        run = session.get(RecommendationRun, body["run_id"])
        results = list(run.results)
        assert run.request_id == "run-check-0001" and run.product.product_name == "Smartphone"
        assert run.status == "ok" and run.top_n == 4
        assert [r.material_rank for r in results] == [1, 2, 3, 4]
        assert [r.recommended_material_id for r in results] == [x["material_id"] for x in body["recommendations"]]
        assert results[0].material.material_id == body["recommendations"][0]["material_id"]
        assert all(r.product_id == 2 for r in results)


def test_inline_recommendation_is_saved_without_product_link(client, db):
    body = post(client, "/recommend", {"product": {"category": "Food", "product_weight_kg": 1.0,
                                                   "fragility_index": 1, "shipping_type": "Road"}}).get_json()
    with db.session() as session:
        run = session.get(RecommendationRun, body["run_id"])
        assert run.product_id is None and run.product_snapshot["category"] == "Food"


def test_database_failure_does_not_lose_the_prediction(make_app, monkeypatch):
    app = make_app()
    db = app.extensions["ecopackai"].db

    def broken_session():
        raise RuntimeError("database down")
    app.test_client().get("/health")
    app.extensions["ecopackai"].service.load()              # models load from the working database first
    monkeypatch.setattr(db, "session", broken_session)
    body = post(app.test_client(), "/predict", {"material": material(5)}).get_json()
    assert body["status"] == "success" and body["predictions"][0]["predicted_cost_usd"] > 0
    assert "could not be saved" in " ".join(body["warnings"])


# =========================================================================
# Caching
# =========================================================================

def test_identical_request_is_served_from_cache(make_app):
    client = make_app().test_client()
    request = {"materials": [material(i) for i in range(20)], "product": PRODUCT}
    first = post(client, "/predict", request)
    second = post(client, "/predict", request)
    assert first.headers["X-Cache"] == "MISS" and second.headers["X-Cache"] == "HIT"
    assert second.get_json()["cached"] is True
    one, two = first.get_json(), second.get_json()
    for key in ("predictions", "model", "mode", "product", "count", "warnings"):
        assert one[key] == two[key]
    assert one["request_id"] != two["request_id"]


def test_cache_makes_repeat_requests_faster(make_app):
    client = make_app().test_client()
    request = {"materials": [material(i) for i in range(50)], "product": PRODUCT}
    post(client, "/predict", request)                         # loads models, fills the cache
    timings = {}
    for label, headers in (("miss", {**CLIENT}), ("hit", {**CLIENT})):
        body = {**request, "options": {"mode": "balanced"}} if label == "miss" else request
        started = time.perf_counter()
        response = post(client, "/predict", body, headers=headers)
        timings[label] = time.perf_counter() - started
        assert response.headers["X-Cache"] == label.upper()
    assert timings["hit"] < timings["miss"] / 2


def test_key_order_does_not_matter_for_the_cache(make_app):
    client = make_app().test_client()
    row = material(7)
    post(client, "/predict", {"material": row})
    reordered = dict(reversed(list(row.items())))
    assert post(client, "/predict", {"material": reordered}).headers["X-Cache"] == "HIT"


def test_recommend_is_cached_and_still_saved(make_app, db):
    client = make_app().test_client()
    before = _count(db, RecommendationRun, product_id=3)
    first = post(client, "/recommend", {"product_id": 3})
    second = post(client, "/recommend", {"product_id": 3})
    assert (first.headers["X-Cache"], second.headers["X-Cache"]) == ("MISS", "HIT")
    assert first.get_json()["recommendations"] == second.get_json()["recommendations"]
    assert _count(db, RecommendationRun, product_id=3) == before + 2       # both calls are audited
    with db.session() as session:
        assert session.get(RecommendationRun, second.get_json()["run_id"]).cached is True


def test_cache_can_be_disabled(make_app):
    client = make_app(CACHE_ENABLED=False).test_client()
    post(client, "/predict", {"material": material(8)})
    assert post(client, "/predict", {"material": material(8)}).headers["X-Cache"] == "BYPASS"


def test_invalid_requests_are_never_cached(make_app):
    app = make_app()
    client = app.test_client()
    bad = {"material": material(0, material_type="Glass")}
    assert post(client, "/predict", bad).status_code == 400
    assert post(client, "/predict", bad).status_code == 400
    assert app.extensions["ecopackai"].cache.stats()["entries"] == 0


# =========================================================================
# Authentication and authorisation
# =========================================================================

@pytest.mark.parametrize("path, body", [("/predict", {"material": material(0)}), ("/recommend", {"product_id": 1})])
def test_protected_endpoints_reject_missing_key(client, path, body):
    response = client.post(path, json=body)
    assert response.status_code == 401 and response.get_json()["error"]["code"] == "unauthorized"


def test_wrong_key_is_rejected(client):
    assert post(client, "/predict", {"material": material(0)}, headers={"X-API-Key": "guess"}).status_code == 401


def test_bearer_token_is_accepted(client):
    response = post(client, "/predict", {"material": material(0)},
                    headers={"Authorization": f"Bearer {CLIENT_KEY}"})
    assert response.status_code == 200


def test_admin_key_can_use_client_endpoints(client):
    assert post(client, "/predict", {"material": material(0)}, headers=ADMIN).status_code == 200


def test_admin_routes_need_admin_key(client):
    assert client.get("/admin/stats").status_code == 401
    assert client.get("/admin/stats", headers=CLIENT).status_code == 403
    assert client.post("/admin/cache/clear", headers=CLIENT).status_code == 403
    assert client.get("/admin/stats", headers={"Authorization": f"Bearer {ADMIN_KEY}"}).status_code == 200


def test_admin_stats_and_cache_clear(make_app):
    client = make_app().test_client()
    post(client, "/predict", {"material": material(9)})
    stats = client.get("/admin/stats", headers=ADMIN).get_json()
    assert stats["cache"]["entries"] == 1 and stats["database"]["rows"]["materials"] == 403
    assert "***" in stats["database"]["url"] or stats["database"]["backend"] == "sqlite"
    assert client.post("/admin/cache/clear", headers=ADMIN).get_json()["entries_removed"] == 1
    assert post(client, "/predict", {"material": material(9)}).headers["X-Cache"] == "MISS"


def test_open_endpoints_need_no_key(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert client.get("/schema").status_code == 200


def test_production_refuses_to_start_without_keys(make_app):
    with pytest.raises(RuntimeError, match="API_KEYS"):
        make_app(ENV_NAME="production", API_KEYS=(), ADMIN_API_KEYS=())


def test_development_without_keys_runs_open(make_app):
    client = make_app(API_KEYS=(), ADMIN_API_KEYS=()).test_client()
    assert client.post("/predict", json={"material": material(0)}).status_code == 200


# =========================================================================
# Headers and logging
# =========================================================================

def test_request_id_is_returned_and_can_be_supplied(client):
    generated = client.get("/health")
    assert len(generated.headers["X-Request-ID"]) == 12
    assert client.get("/health", headers={"X-Request-ID": "my-trace-42"}).headers["X-Request-ID"] == "my-trace-42"


def test_malformed_request_id_is_rejected(client):
    assert client.get("/health", headers={"X-Request-ID": "bad id with spaces"}).status_code == 400


def test_security_headers_are_set(client):
    headers = client.get("/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff" and headers["Cache-Control"] == "no-store"


def _log_lines(app, name):
    path = f"{app.config['LOG_DIR']}/{name}"
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_logs_are_structured_and_separated(make_app):
    app = make_app()
    client = app.test_client()
    post(client, "/predict", {"material": material(10)}, headers={**CLIENT, "X-Request-ID": "log-check-0001"})
    post(client, "/predict", {"material": material(10)}, headers={"X-API-Key": "stolen-key-attempt"})

    app_lines = _log_lines(app, "app.log")
    access = [x for x in app_lines if x.get("event") == "request" and x["request_id"] == "log-check-0001"]
    prediction = [x for x in app_lines if x.get("event") == "prediction" and x["request_id"] == "log-check-0001"]
    assert access and prediction
    assert access[0]["status"] == 200 and access[0]["level"] == "INFO" and "duration_ms" in access[0]
    assert {"timestamp", "level", "logger", "message", "request_id"} <= set(access[0])
    assert prediction[0]["count"] == 1 and prediction[0]["cache"] in {"MISS", "HIT"}

    security = _log_lines(app, "security.log")
    denied = [x for x in security if x.get("event") == "auth_denied"]
    assert denied and denied[-1]["reason"] == "invalid_key" and denied[-1]["level"] == "WARNING"
    assert all(x["logger"] == "ecopackai.security" for x in security)

    raw = open(f"{app.config['LOG_DIR']}/security.log", encoding="utf-8").read() + \
        open(f"{app.config['LOG_DIR']}/app.log", encoding="utf-8").read()
    assert "stolen-key-attempt" not in raw and CLIENT_KEY not in raw        # keys are never logged


def test_errors_are_logged_with_traceback(make_app, monkeypatch):
    app = make_app()
    monkeypatch.setattr(app.extensions["ecopackai"].service, "load",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom for the log")))
    post(app.test_client(), "/predict", {"material": material(0)}, headers={**CLIENT, "X-Request-ID": "err-0001"})
    errors = [x for x in _log_lines(app, "app.log") if x["level"] == "ERROR" and x["request_id"] == "err-0001"]
    assert any("boom for the log" in x.get("exception", "") for x in errors)


# =========================================================================
# Schema document
# =========================================================================

def test_schema_document_is_up_to_date():
    saved = json.loads((ROOT / "docs" / "api_schema.json").read_text(encoding="utf-8"))
    assert saved == build_api_schema(), "Re-run: python backend/routes/predict.py"


def test_schema_route_serves_the_schema(client):
    assert client.get("/schema").get_json() == build_api_schema()
