# Test Report — EcoPackAI Backend

**Date:** 2026-10-04 · **Python** 3.11.16 · **pytest** 8.3.2 · **Databases:** SQLite 3 and PostgreSQL 16.2

```bash
pytest tests -v                                              # SQLite (default)
set TEST_DATABASE_URL=postgresql://user:pass@host:5432/db    # Windows cmd; empty test database
pytest tests -v --cov=backend --cov=src --cov-report=term    # PostgreSQL + coverage
```

CI (`.github/workflows/ci.yml`) runs both on every push, the PostgreSQL run against a
`postgres:16` service container.

## 1. Results

| Test file | Type | Tests | SQLite | PostgreSQL |
|---|---|---|---|---|
| `tests/test_api.py` | API unit + integration | 67 | ✅ pass | ✅ pass |
| `tests/test_backend_units.py` | Unit (cache, auth, logging, settings, validation) | 27 | ✅ pass | ✅ pass |
| `tests/test_database.py` | Database integration | 15 | ✅ pass | ✅ pass |
| `tests/test_predictor.py` | Packaged models | 17 | ✅ pass | ✅ pass |
| `tests/test_ranker.py` | Ranking logic | 17 | ✅ pass | ✅ pass |
| `tests/test_data_quality.py` | Data quality | 19 | ✅ pass | ✅ pass |
| **Total** | | **162** | **162 passed** | **162 passed** |

Run time about 12 s (SQLite) and 26 s (PostgreSQL with coverage). The 4 warnings are
expected: one test material lies outside the training range, and the predictor warns about it.

## 2. What Is Tested

| Area | Examples |
|---|---|
| Input validation (unit) | Missing fields, wrong types (`True` is not a number), unknown categories, bounds, all errors reported together, `product_id` and `top_n` rules |
| Prediction logic | Single and batch inputs, equal to the packaged predictor; final scores equal the ranking engine; `/recommend` equals `outputs/material_rankings.csv` for 3 products |
| Error handling | 400 / 404 / 405 / 413 / 415 / 500 as JSON; internal details hidden; database failure still returns the prediction with a warning |
| Database connectivity | Ping, tables exist, schema equals the models, CSV values read back unchanged, seeding idempotent |
| Database mapping | Product ↔ run ↔ result ↔ material relationships, foreign key rejects unknown materials, cascade delete, server-side timestamps |
| Migrations | Upgrade → downgrade → upgrade on a fresh database; `init-db` creates a missing database folder |
| Endpoints | `/health` (< 100 ms, no model or database access), `/ready` (ready / not ready), `/predict`, `/recommend`, `/schema`, `/admin/stats`, `/admin/cache/clear` |
| Authentication / authorisation | No key → 401, wrong key → 401, client key on admin route → 403, Bearer token accepted, admin key works everywhere, production without keys refuses to start, development without keys runs open |
| Caching (unit) | TTL expiry (fake clock), LRU eviction, values protected from outside changes, disabled cache, statistics, key independent of JSON key order, new key after model/config change |
| Caching (integration) | `X-Cache` MISS → HIT, identical results, hit at least 2× faster than miss, cached calls still saved, errors never cached, admin clear |
| Logging | JSON fields present, request IDs match, prediction summaries, denials only in `security.log`, tracebacks logged on errors, API keys never written to any log |
| Headers | Request ID generated or accepted, malformed `X-Request-ID` rejected, security headers set |
| Response schema | Same keys for every success response; `docs/api_schema.json` equals the generated schema |
| Generated docs | `docs/data_dictionary.md` and `backend/db/schema.sql` equal what the models generate |

**The tests can fail.** Three deliberate bugs were planted and each was caught: admin
check removed (1 test failed), cache key ignoring the request body (32 failed),
prediction history not saved (1 failed).

## 3. Coverage

`pytest --cov=backend --cov=src`, SQLite run:

| Module | Statements | Coverage |
|---|---|---|
| `backend/app.py` | 77 | 96% |
| `backend/cache.py` | 53 | 100% |
| `backend/db/__init__.py` | 47 | 100% |
| `backend/db/seed.py` | 24 | 92% |
| `backend/logging_setup.py` | 37 | 95% |
| `backend/manage.py` | 66 | 73% |
| `backend/middleware/auth.py` | 53 | 98% |
| `backend/middleware/request_context.py` | 31 | 100% |
| `backend/migrations/env.py` | 31 | 81% |
| `backend/migrations/versions/0001_initial_schema.py` | 33 | 100% |
| `backend/models/__init__.py` | 95 | 100% |
| `backend/routes/admin.py` | 23 | 91% |
| `backend/routes/common.py` | 20 | 95% |
| `backend/routes/predict.py` | 192 | 94% |
| `backend/routes/recommend.py` | 94 | 89% |
| `backend/services.py` | 65 | 91% |
| `backend/settings.py` | 18 | 89% |
| `src/inference/predictor.py` | 86 | 95% |
| `src/recommendation/ranker.py` | 130 | 81% |
| `src/inference/build_metadata.py` | 52 | 0% |
| **Total** | **1,228** | **88%** |

Not covered: the command-line entry points (`manage.py` argument handling,
`build_metadata.py`, the ranker's `main()`), which tests exercise as functions instead,
and a few defensive branches (e.g. database errors in rarely used paths).

## 4. Manual End-to-End Checks

Beyond the automated tests, the real server (`python backend/app.py`, production mode,
API keys set) was started from the project folder against PostgreSQL and called over HTTP:

| Check | Result |
|---|---|
| `GET /health` | 200 in 5 ms, `models_loaded: false` |
| `GET /ready` | 200, database / schema / materials all `ok` |
| `POST /recommend` (product 92), first call | 200 in 0.87 s (includes one-off model loading), `X-Cache: MISS` |
| Same request again | 200 in 0.02 s, `X-Cache: HIT` |
| No API key | 401 |
| Client key on `/admin/stats` | 403 |
| Admin key on `/admin/stats` | 200, database URL shown with password hidden |
| Log files | `app.log` and `security.log` created; both denials recorded in `security.log` |

The Docker startup sequence (`manage.py init-db`, then `app.py`) was simulated with only
the folders the Dockerfile copies, against PostgreSQL: tables created, data loaded, API
ready. Docker itself is not installed on the development machine, so the container image
was not built.

## 5. Bugs Found and Fixed During Testing

| Bug | Found by | Fix |
|---|---|---|
| Migration used PostgreSQL-only `now()` as timestamp default (fails on SQLite) | Review of the generated migration | `sa.func.now()`, which works on both |
| Materials read from the database had SQLAlchemy `quoted_name` column names, which scikit-learn rejects | Smoke test on PostgreSQL | Column names converted to plain `str` |
| `init-db` failed on a fresh checkout because the `instance/` folder did not exist | Running `init-db` in the real project | Folder created before connecting; regression test added |
| Rounding noise (~1e-14) between Random Forest calls made exact-equality tests flaky | Repeated test runs | Tolerance of 1e-9 in tests |
