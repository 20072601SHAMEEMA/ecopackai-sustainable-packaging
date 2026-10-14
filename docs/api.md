# EcoPackAI API

Flask API that serves the packaged cost and CO2 models and the ranking logic.

| File | Role |
|---|---|
| `backend/app.py` | Entry point: wires settings, logging, database, cache, middleware; `/health`, `/ready`, JSON errors |
| `backend/routes/predict.py` | `/predict` and `/schema`: input validation, inference, scoring, prediction history |
| `backend/routes/recommend.py` | `/recommend`: rank the catalogue for a product, save the run |
| `backend/routes/admin.py` | `/admin/stats`, `/admin/cache/clear` (admin key) |
| `backend/middleware/` | `auth.py` (API keys, roles), `request_context.py` (request IDs, header checks, access log) |
| `backend/settings.py` | All settings from environment variables / `.env` |
| `docs/api_schema.json` | Request/response JSON Schema (generated, do not edit) |
| `tests/test_api.py` | API unit and integration tests (Flask test client, no server needed) |

Related: `docs/database.md` (tables, migrations), `docs/caching.md` (cache, benchmark),
`docs/logging.md` (log format), `docs/test_report.md` (test results, coverage).

The API layer contains no ML logic. It validates requests and calls
`MaterialPredictor` (`src/inference/predictor.py`) and the ranking functions
(`src/recommendation/ranker.py`).

## 1. Running the API

From the project root, with the `ecopackai` environment active:

```bash
copy .env.example .env               # once; then edit the keys in .env
python backend/manage.py init-db     # once: create the tables and load the CSVs
python backend/app.py
```

The server listens on `http://127.0.0.1:5000`. The same server also serves the website
(`/` and `/index.html`, `/predict.html`, `/results.html`, `/dashboard.html`, `/static/...`;
see `docs/ui_flow.md`). Settings come from environment variables
or the `.env` file (full list in `backend/settings.py`):

| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | `development` | `production` turns off debug mode and refuses to start without API keys |
| `APP_HOST`, `APP_PORT` | `127.0.0.1`, `5000` | Use host `0.0.0.0` inside Docker |
| `DATABASE_URL` | SQLite `instance/ecopackai.db` | e.g. `postgresql://user:pass@host:5432/db` |
| `API_KEYS` | not set | Comma-separated client keys (`/predict`, `/recommend`) |
| `ADMIN_API_KEYS` | not set | Comma-separated admin keys (`/admin/*` and everything else) |
| `CACHE_ENABLED`, `CACHE_TTL_SECONDS`, `CACHE_MAX_ENTRIES` | `true`, `300`, `1024` | Response cache (`docs/caching.md`) |
| `LOG_DIR`, `LOG_LEVEL` | `logs/`, `INFO` | Log files (`docs/logging.md`) |

`python backend/app.py` uses Flask's built-in server, which is meant for development.
For a public deployment, run the same app behind a production WSGI server
(e.g. `waitress-serve --call app:create_app` from the `backend` folder).

## 2. `GET /health`

Liveness check for monitoring and deployment. No authentication, no model loading,
answers in a few milliseconds. It does not touch the database either.

```bash
curl http://127.0.0.1:5000/health
```

```json
{
  "status": "ok",
  "service": "ecopackai-api",
  "version": "1.1.0",
  "environment": "development",
  "uptime_seconds": 12.4,
  "models_loaded": false
}
```

`models_loaded` is `false` until the first `/predict` or `/recommend` request loads
the models (about 0.5 s, once). It is informational: the service is healthy either way.

### `GET /ready`

Readiness check for deployments: database reachable, schema at the latest migration,
materials loaded. No authentication. `200 {"status": "ready", ...}` or
`503 {"status": "not_ready", ...}`:

```json
{"status": "ready", "checks": {"database": "ok", "schema": "ok", "materials": "ok"}}
```

`schema: "migration needed"` or `materials: "empty"` means: run
`python backend/manage.py init-db`.

## Authentication

| Endpoint | Key needed |
|---|---|
| `GET /health`, `GET /ready`, `GET /schema` | none |
| `POST /predict`, `POST /recommend` | client or admin key |
| `GET /reports/<run_id>.csv`, `GET /reports/<run_id>.pdf` | client or admin key |
| `GET /admin/stats`, `POST /admin/cache/clear` | admin key |

Send the key in either header:

```
X-API-Key: <key>
Authorization: Bearer <key>
```

- No key or an unknown key → `401 unauthorized`; a client key on an admin route →
  `403 forbidden`. Each denial is written to `logs/security.log` with the reason and an
  8-character key fingerprint (never the key itself).
- Keys are compared in constant time, and every configured key is checked, so response
  timing does not reveal valid keys.
- If no keys are configured: in `development` the API runs **without authentication** and
  logs a warning at startup; in `production` it refuses to start.
- Generate a strong key, e.g. `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## 3. `POST /predict`

Predicts cost per unit (USD) and CO2 per kg for one or more materials. With a
`product`, it also scores and ranks the materials for that product using the same
logic as `src/recommendation/ranker.py`. Needs a client key. Every predicted material
is saved to `prediction_history`; identical requests are served from the cache
(`X-Cache: HIT`).

### Request

Send JSON (`Content-Type: application/json`) with **exactly one** of
`material` (one object) or `materials` (a list, max 100).

```json
{
  "materials": [
    {
      "material_id": "MAT_0154",
      "material_type": "Cardboard",
      "packaging_type": "Cardboard Boxes",
      "supplier_region": "EMEA",
      "recyclability_category": "High",
      "recyclability_percent": 100,
      "recycled_content_percent": 78.0,
      "reusability_percent": 47.0,
      "biodegradation_time_days": 157.0,
      "end_of_life_disposal_percent": 5.0,
      "carbon_footprint_kg_co2_per_unit": 0.76,
      "waste_reduction_impact_percent": 61.0,
      "sustainability_target_progress_percent": 90.0,
      "load_handling_score": 6.0,
      "moisture_resistance_score": 5.0,
      "thermal_resistance_score": 5.0,
      "annual_usage_units": 100871.0,
      "total_material_weight_tons": 847.0,
      "supplier_sustainability_compliance_percent": 90.0,
      "suitable_product_categories": "E-commerce, Food & Beverage, Consumer Goods, Apparel"
    }
  ],
  "product": {
    "product_id": 1,
    "product_name": "Chocolate Box",
    "category": "Food",
    "product_weight_kg": 0.5,
    "fragility_index": 2,
    "shipping_type": "Air"
  },
  "options": {"mode": "balanced"}
}
```

**Material fields.** All 18 model inputs are required (full list, types and allowed
values in `docs/api_schema.json` or `GET /schema`):

| Field kind | Rule |
|---|---|
| `material_type`, `packaging_type`, `supplier_region` | Text, one of the values the model was trained on |
| `recyclability_category` | `Low`, `Medium` or `High` |
| `*_percent` fields | Number 0–100 |
| `*_score` fields | Number 0–10 |
| Other numbers (days, tons, units, kg CO2) | Number ≥ 0 |
| `material_id` | Optional text, echoed back |
| `suitable_product_categories` | Comma-separated text; required only when `product` is sent |

**Product (optional).** `category` (one of the 6 categories in
`config/ranking_weights.yaml`), `product_weight_kg` (> 0), `fragility_index`
(whole number 1–5), `shipping_type` (`Air`, `Road`, `Sea`); `product_id` and
`product_name` are optional.

**Options (optional).** `mode`: `balanced` (default), `sustainability_first`,
`cost_first`. Used only with a product.

### Success response (200)

```json
{
  "status": "success",
  "request_id": "3f9c1a2b7d4e",
  "model": {
    "package_version": "1.0.0",
    "cost": {"name": "RandomForestRegressor", "version": 1, "target": "cost_per_unit_usd", "unit": "USD per unit"},
    "co2": {"name": "XGBRegressor", "version": 1, "target": "co2_emission_per_kg", "unit": "kg CO2 per kg of material"}
  },
  "mode": "balanced",
  "product": {"product_id": 1, "product_name": "Chocolate Box", "category": "Food",
              "product_weight_kg": 0.5, "fragility_index": 2, "shipping_type": "Air"},
  "count": 1,
  "predictions": [
    {
      "index": 0,
      "material_id": "MAT_0154",
      "predicted_cost_usd": 2.7885,
      "predicted_co2_per_kg": 0.5102,
      "scores": {"co2": 0.9286, "cost": 0.9136, "sustainability": 0.8649,
                 "suitability": 0.5333, "final_score": 81.5715},
      "eligible": true,
      "rank": 1
    }
  ],
  "warnings": [],
  "cached": false,
  "processing_ms": 127.2
}
```

| Field | Meaning |
|---|---|
| `predicted_cost_usd`, `predicted_co2_per_kg` | Model predictions |
| `scores.co2/cost/sustainability` | 0–1, 1 = best, scaled against the whole material catalogue (same as the ranking engine) |
| `scores.suitability`, `scores.final_score` | Only with a product: product-specific fit (0–1) and weighted total (0–100) for the chosen mode |
| `eligible`, `rank` | Only with a product: passes all business constraints; rank among eligible materials (1 = best), `null` if not eligible |
| `warnings` | Non-fatal notes, e.g. a value outside the training range |
| `cached` | `true` if the result came from the response cache (also header `X-Cache`) |

The response always has the same keys; without a product, `mode` and `product`
are `null` and `eligible`/`rank` are omitted. The `X-Request-ID` header repeats
`request_id` for log tracing.

### Error responses

Every error is JSON with the same shape:

```json
{
  "status": "error",
  "request_id": "a81c2e9f0b13",
  "error": {
    "code": "validation_error",
    "message": "2 problem(s) in the request.",
    "details": [
      {"field": "materials[0].material_type", "message": "'Glass' is not allowed; use one of ['Cardboard', 'Paper/Bio-Based', 'Plastic', 'Steel']"},
      {"field": "materials[1].recyclability_percent", "message": "must be <= 100, got 140"}
    ]
  }
}
```

All problems in a request are reported together, each with its exact field path.

| HTTP | `error.code` | When |
|---|---|---|
| 400 | `validation_error` | Missing field, wrong type, value not allowed, out of bounds, batch over 100, bad structure |
| 400 | `invalid_json` | Body is not valid JSON |
| 400 | `bad_request` | Malformed `X-Request-ID` header |
| 401 | `unauthorized` | API key missing or unknown |
| 403 | `forbidden` | Client key on an admin endpoint |
| 404 | `not_found` | Unknown URL, `/recommend` with an unknown `product_id`, or an unknown report `run_id` |
| 405 | `method_not_allowed` | e.g. `GET /predict` |
| 413 | `request_entity_too_large` | Body over 1 MB |
| 415 | `unsupported_media_type` | Body not sent as JSON |
| 500 | `internal_error` | Unexpected failure; details are logged with the `request_id`, never sent to the client |
| 503 | `database_unavailable` | The database cannot be reached (`/recommend` product lookup, `/admin/stats`) |

## 4. `POST /recommend`

Ranks the whole material catalogue for one product and returns the top N, with the
same logic and scores as `src/recommendation/ranker.py` and `outputs/material_rankings.csv`.
Needs a client key. Each call is saved as one `recommendation_runs` row plus one
`recommendation_logs` row per recommended material; identical requests are cached.

### Request

Exactly one of `product_id` (a product in the `products` table) or `product` (inline,
same fields and rules as the `/predict` product):

```json
{"product_id": 1, "options": {"mode": "balanced", "top_n": 3}}
```

```json
{"product": {"category": "Electronics", "product_weight_kg": 0.3, "fragility_index": 5, "shipping_type": "Air"}}
```

`options.mode`: `balanced` (default), `sustainability_first`, `cost_first`.
`options.top_n`: 1–20 (default 5, from `config/ranking_weights.yaml`).

### Success response (200)

```json
{
  "status": "success",
  "request_id": "060eace8a85f",
  "run_id": 1,
  "model": {"package_version": "1.0.0",
            "cost": {"name": "RandomForestRegressor", "version": 1, "target": "cost_per_unit_usd", "unit": "USD per unit"},
            "co2": {"name": "XGBRegressor", "version": 1, "target": "co2_emission_per_kg", "unit": "kg CO2 per kg of material"}},
  "mode": "balanced",
  "product": {"product_id": 1, "product_name": "Chocolate Box", "category": "Food",
              "product_weight_kg": 0.5, "fragility_index": 2, "shipping_type": "Air"},
  "top_n": 3,
  "n_candidates": 153,
  "result": "ok",
  "recommendations": [
    {"rank": 1, "material_id": "MAT_0154", "material_type": "Cardboard", "packaging_type": "Cardboard Boxes",
     "final_score": 81.5715, "predicted_cost_usd": 2.7885, "predicted_co2_per_kg": 0.5102, "recyclability_percent": 100.0,
     "scores": {"co2": 0.9286, "cost": 0.9136, "suitability": 0.5333, "sustainability": 0.8649}},
    {"rank": 2, "material_id": "MAT_0237", "material_type": "Cardboard", "packaging_type": "Cardboard Boxes",
     "final_score": 80.5389, "predicted_cost_usd": 2.8263, "predicted_co2_per_kg": 0.509, "recyclability_percent": 98.0,
     "scores": {"co2": 0.929, "cost": 0.9121, "suitability": 0.5067, "sustainability": 0.8426}},
    {"rank": 3, "material_id": "MAT_0051", "material_type": "Plastic", "packaging_type": "Bubble Wrap (Minimal Use)",
     "final_score": 74.0937, "predicted_cost_usd": 1.2369, "predicted_co2_per_kg": 1.4764, "recyclability_percent": 78.0,
     "scores": {"co2": 0.5887, "cost": 0.9759, "suitability": 0.86, "sustainability": 0.3772}}
  ],
  "warnings": [],
  "cached": false,
  "processing_ms": 334.9
}
```

- `n_candidates`: materials that passed all business constraints for this product.
- `result: "no_valid_material"` with an empty list (still 200) when no material passes,
  e.g. product 775 (fragile wine bottle shipped by sea); see `docs/material_ranking.md`.
- `run_id`: the saved row in `recommendation_runs` (`null` plus a warning if saving failed).
- Inline products are saved with `product_id = NULL` and a JSON snapshot.

## 5. Admin Endpoints (admin key)

| Endpoint | Returns |
|---|---|
| `GET /admin/stats` | Uptime; database backend, URL (password hidden) and row counts per table; cache statistics (entries, hits, misses, hit rate, evictions, expirations); model versions and catalogue source |
| `POST /admin/cache/clear` | `{"status": "success", "entries_removed": n}`; logged in `security.log` |

## 5b. Report Export (client key)

| Endpoint | Returns |
|---|---|
| `GET /reports/<run_id>.csv` | Recommendation results of that run (`text/csv`, UTF-8 with BOM) |
| `GET /reports/<run_id>.pdf` | Sustainability summary of that run (`application/pdf`) |

`run_id` comes from the `/recommend` response. Files are built from the saved run, so they
match the response exactly, and are sent as downloads named
`ecopackai_recommendations_<product>_<YYYYMMDD-HHMMSS>_run<id>.csv` /
`ecopackai_sustainability_summary_<product>_<YYYYMMDD-HHMMSS>_run<id>.pdf`.
Formats and naming rules: `docs/analytics.md`.

## 6. `GET /schema`

Returns the JSON Schema of requests and responses (identical to
`docs/api_schema.json`). The schema is generated from the model metadata and the
ranking config, so allowed values always match the deployed models. After
retraining or changing the config, regenerate it:

```bash
python backend/routes/predict.py
```

`tests/test_api.py` fails if the saved file is out of date.

## 7. Security Measures

- API-key authentication with client and admin roles (`backend/middleware/auth.py`);
  production refuses to start without keys.
- Strict input validation: types, allowed values, bounds; unknown values rejected
  before reaching the model.
- Header checks: JSON required for request bodies (415), `X-Request-ID` format checked (400).
- Body size limit (1 MB), batch limit (100 materials), `top_n` limit (20).
- Response headers `X-Content-Type-Options: nosniff` and `Cache-Control: no-store`.
- No stack traces, keys or database passwords in responses or logs; errors carry a
  `request_id` instead.
- Separate security log (`logs/security.log`) for denials, rejected headers and admin actions.

## 8. Validation Checklists

| Check | Evidence |
|---|---|
| Application starts without errors | `python backend/app.py`; `create_app()` in every test |
| `/health` responds within milliseconds | ~3 ms over HTTP; test asserts < 100 ms |
| Correct status message | `{"status": "ok", ...}` |
| No model loading for health | Test asserts `models_loaded` stays `false` after `/health` |
| Valid inputs return predictions | Single, batch and product tests; values equal the predictor |
| Invalid inputs return descriptive errors | Missing, wrong type, bad category, out of bounds, bad product, bad mode |
| Schema enforcement prevents malformed requests | Empty body, both/neither keys, wrong shapes, non-JSON, broken JSON, oversized |
| Consistent response format | Same keys for single, batch and product requests |
| Integrates with ranking logic | API final scores and ranks equal `rank_for_product()`; `/recommend` equals `outputs/material_rankings.csv` |
| Secure endpoints reject unauthorized requests | Missing/wrong key → 401, client key on admin → 403, Bearer token accepted, production without keys refuses to start |
| Logs capture meaningful runtime events | Tests read `app.log` / `security.log`: request lines, prediction summaries, denials, tracebacks; keys never logged |
| Cached responses reduce latency | `X-Cache: HIT` tests; hit at least 2× faster than miss (benchmark: 1.8×–34×) |
| Database tables created and mapped | `tests/test_database.py` (migrations, relationships, foreign keys, CSV equality) |
