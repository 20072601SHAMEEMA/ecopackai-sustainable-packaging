# Logging — Format and Configuration

**Configuration:** `config/logging.yaml` · **Code:** `backend/logging_setup.py`,
`backend/middleware/request_context.py` · **Tests:** logging tests in `tests/test_api.py`

## 1. Log Files

| File | Logger | Contents |
|---|---|---|
| `logs/app.log` | `ecopackai`, `ecopackai.access` | Startup, one line per API request, prediction and recommendation summaries, errors with tracebacks |
| `logs/security.log` | `ecopackai.security` | Authentication failures, rejected headers, admin actions, "auth disabled" warnings |
| console (stdout) | all of the above | Same lines, for development and container logs |

- Files rotate at 5 MB (`app.log` keeps 5 old files, `security.log` keeps 10).
- Folder: `LOG_DIR` (default `logs/`, ignored by git). Level: `LOG_LEVEL` (default `INFO`).
- Security events go **only** to `security.log` (and the console), so they can be kept
  longer and reviewed separately.

## 2. Line Format

Every line is one JSON object (JSON Lines), so logs can be filtered by any field.

**Always present**

| Field | Example | Meaning |
|---|---|---|
| `timestamp` | `2026-10-04T14:51:54.118+00:00` | UTC, millisecond precision |
| `level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `logger` | `ecopackai.access` | Which logger wrote it |
| `message` | `POST /predict 200` | Human-readable summary |
| `request_id` | `e54ff536fe70` | Same ID as the `X-Request-ID` response header; `null` outside a request |

**Event-specific fields** (`event` names the kind of line):

| `event` | Logger | Extra fields |
|---|---|---|
| `startup` | ecopackai | `environment`, `database` (password hidden), `cache_enabled` |
| `request` | ecopackai.access | `method`, `path`, `status`, `duration_ms`, `remote_addr`, `auth_role`, `key_fingerprint`, `cache` |
| `models_loaded` | ecopackai | `catalogue_source` (`database` / `csv`), `catalogue_size` |
| `prediction` | ecopackai | `count`, `mode`, `cache`, `with_product`, `warnings` |
| `recommendation` | ecopackai | `product_id`, `mode`, `result`, `n_candidates`, `cache`, `run_id` |
| `unhandled_error`, `history_save_failed`, `run_save_failed`, `db_error`, `not_ready` | ecopackai | `exception` (full traceback) |
| `auth_denied` | ecopackai.security | `reason` (`missing_key` / `invalid_key` / `insufficient_role`), `status`, `method`, `path`, `remote_addr`, `key_fingerprint` |
| `bad_header` | ecopackai.security | `header`, `path`, `remote_addr` |
| `cache_cleared` | ecopackai.security | `entries_removed` |
| `auth_disabled` | ecopackai.security | — (startup in development without keys) |

**Severity of request lines:** `INFO` for 2xx/3xx, `WARNING` for 4xx, `ERROR` for 5xx.

## 3. Examples

```json
{"timestamp": "2026-10-04T14:51:54.118+00:00", "level": "INFO", "logger": "ecopackai", "message": "Prediction served", "request_id": "e54ff536fe70", "event": "prediction", "count": 3, "mode": null, "cache": "MISS", "with_product": false, "warnings": 0}
{"timestamp": "2026-10-04T14:51:54.119+00:00", "level": "INFO", "logger": "ecopackai.access", "message": "POST /predict 200", "request_id": "e54ff536fe70", "event": "request", "method": "POST", "path": "/predict", "status": 200, "duration_ms": 434.26, "remote_addr": "127.0.0.1", "auth_role": "client", "key_fingerprint": "61f187c6", "cache": "MISS"}
{"timestamp": "2026-10-04T14:51:17.068+00:00", "level": "WARNING", "logger": "ecopackai.security", "message": "Access denied", "request_id": "a50bb706e99c", "event": "auth_denied", "reason": "invalid_key", "status": 401, "method": "POST", "path": "/predict", "remote_addr": "127.0.0.1", "key_fingerprint": "ca3704aa"}
```

## 4. Request IDs (Tracing)

- Each request gets a 12-character ID, returned in the `X-Request-ID` header and in every
  JSON response (also on errors).
- A client may send its own `X-Request-ID` (8–64 letters, digits, `.`, `_`, `-`) to follow
  one request across systems; malformed values are rejected with 400 and logged.
- The same ID is stored in `prediction_history.request_id` and
  `recommendation_runs.request_id`, so a log line, a response and a database row can be
  matched. A user reporting an error only needs to quote the `request_id`.

## 5. What Is Never Logged

- API keys: only an 8-character fingerprint (start of the key's SHA-256) identifies which
  key was used. A test checks that neither a valid nor a rejected key appears in the logs.
- Database passwords (URLs are logged as `postgresql://user:***@host/db`).
- Full request bodies (only counts and summaries).

## 6. Searching Logs (examples)

```bash
# Everything that happened in one request
findstr "e54ff536fe70" logs\app.log logs\security.log

# All denied requests (PowerShell)
Get-Content logs\security.log | ConvertFrom-Json | Where-Object event -eq auth_denied
```
