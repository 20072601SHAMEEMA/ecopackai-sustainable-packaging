# Response Caching — EcoPackAI

**Code:** `backend/cache.py` (cache), `backend/routes/predict.py` and
`backend/routes/recommend.py` (use) · **Benchmark:** `scripts/benchmark_cache.py` →
`outputs/benchmarks/cache_benchmark.csv` · **Tests:** cache tests in
`tests/test_backend_units.py` and `tests/test_api.py`

## 1. What Is Cached

| Endpoint | Cached | Why |
|---|---|---|
| `POST /predict` | yes | Same materials (and product/mode) always give the same predictions and scores |
| `POST /recommend` | yes | Same product and options always give the same ranking; also skips the product lookup in the database |
| `/health`, `/ready` | no | Must show the live state |
| `/admin/*` | no | Must show the live state |
| Error responses | no | Only successful results are stored |

What is cached is the computed result (predictions, scores, ranking). Every response still
gets its own `request_id` and `processing_ms`, and **every request is still saved to the
database** (`prediction_history`, `recommendation_runs` with `cached = true`), so the audit
trail is complete.

Response header `X-Cache`: `MISS` (computed and stored), `HIT` (served from the cache),
`BYPASS` (cache disabled). The JSON body also contains `"cached": true/false`.

## 2. Configuration

In-memory cache, one per server process. Settings (environment variables or `.env`):

| Setting | Default | Meaning |
|---|---|---|
| `CACHE_ENABLED` | `true` | Turn the cache on/off |
| `CACHE_TTL_SECONDS` | `300` | An entry expires 5 minutes after it was stored |
| `CACHE_MAX_ENTRIES` | `1024` | Beyond this, the least recently used entry is removed |

**Why in-memory and not Redis:** the API runs as a single process, and the cache only
holds small JSON results, so an in-process cache gives the speed-up with no extra service
to run. The cache has a plain get/set/clear interface; with several server processes it can
be backed by Redis (shared between processes) without changing the routes.

## 3. Cache Keys and Invalidation

**Key** = SHA-256 of:
1. the endpoint (`/predict` or `/recommend`),
2. the request body in canonical JSON (sorted keys), so `{"a":1,"b":2}` and
   `{"b":2,"a":1}` share a key,
3. a fingerprint of the model files (from `metadata.json` SHA-256 values),
4. a fingerprint of the ranking config (`config/ranking_weights.yaml`).

**Invalidation strategy:**

| Event | What happens |
|---|---|
| Time passes | Entries expire after `CACHE_TTL_SECONDS` |
| Cache full | Least recently used entry is evicted |
| Model retrained / config edited | New fingerprint → new keys; old entries are never matched again and age out (the models and config are loaded at startup, so restart the API after such changes) |
| Product or material rows edited in the database | Clear with `POST /admin/cache/clear` (admin key), or wait for the TTL |
| Server restart | The cache starts empty |

Values are deep-copied in and out of the cache, so a response can never modify a cached
entry. Access is thread-safe.

## 4. Performance: Before vs After

`python scripts/benchmark_cache.py` sends each request 30 times with the cache off and
30 times with a warm cache, after loading the models (one-off model loading excluded).
Median latency in milliseconds:

**SQLite**

| Request | Cache off | Cache on (warm) | Speed-up |
|---|---|---|---|
| `/predict` — 1 material | 91.7 | 8.0 | 11.4× |
| `/predict` — 20 materials + product | 103.9 | 17.4 | 6.0× |
| `/predict` — 100 materials + product | 185.2 | 45.9 | 4.0× |
| `/recommend` — `product_id` (database lookup) | 26.4 | 14.2 | 1.9× |
| `/recommend` — inline product | 23.1 | 13.0 | 1.8× |

**PostgreSQL 16**

| Request | Cache off | Cache on (warm) | Speed-up |
|---|---|---|---|
| `/predict` — 1 material | 120.0 | 3.5 | 34.1× |
| `/predict` — 20 materials + product | 143.5 | 11.8 | 12.2× |
| `/predict` — 100 materials + product | 175.3 | 40.4 | 4.3× |
| `/recommend` — `product_id` (database lookup) | 19.8 | 6.6 | 3.0× |
| `/recommend` — inline product | 18.0 | 6.4 | 2.8× |

**Reading the numbers:**
- A cache hit skips model inference, scoring against the 403-material catalogue and (for
  `/recommend`) the product lookup.
- What remains on a hit is mostly writing the audit rows (one `prediction_history` row
  per material), which is why 100 materials still take ~40 ms. That cost is deliberate:
  every request must be traceable.
- Numbers come from one Windows laptop and vary between runs; the ratios are what matter.
  The test `test_cache_makes_repeat_requests_faster` checks on every run that a hit is at
  least twice as fast as a miss.

## 5. Monitoring

`GET /admin/stats` (admin key) returns entries, hits, misses, hit rate, evictions and
expirations. Every access-log line in `logs/app.log` includes `"cache": "HIT" | "MISS" | "BYPASS"`.
