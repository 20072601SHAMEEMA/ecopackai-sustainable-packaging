"""
EcoPackAI - Backend Settings
Module: Flask Backend

All settings come from environment variables (or a .env file in the project
root, see .env.example), with safe defaults for local development.

| Variable            | Default                         | Meaning                                  |
|---------------------|---------------------------------|------------------------------------------|
| APP_ENV             | development                     | development / production                 |
| APP_HOST, APP_PORT  | 127.0.0.1, 5000                 | where the server listens                 |
| DATABASE_URL        | sqlite:///<root>/instance/...   | any SQLAlchemy URL, e.g. postgresql://   |
| API_KEYS            | (none)                          | comma-separated client keys              |
| ADMIN_API_KEYS      | (none)                          | comma-separated admin keys               |
| CACHE_ENABLED       | true                            | in-memory response cache on/off          |
| CACHE_TTL_SECONDS   | 300                             | how long a cached response stays valid   |
| CACHE_MAX_ENTRIES   | 1024                            | oldest entries are evicted beyond this   |
| LOG_DIR             | <root>/logs                     | where app.log and security.log are kept  |
| LOG_LEVEL           | INFO                            | DEBUG / INFO / WARNING / ERROR           |
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE = f"sqlite:///{(ROOT / 'instance' / 'ecopackai.db').as_posix()}"


def _split(value):
    return tuple(part.strip() for part in (value or "").split(",") if part.strip())


def _flag(value, default):
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> dict:
    """Read settings from the environment (after loading .env, if present)."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
    except ImportError:            # python-dotenv is optional
        pass

    env = os.environ.get
    return {
        "ENV_NAME": env("APP_ENV", "development"),
        "HOST": env("APP_HOST", "127.0.0.1"),
        "PORT": int(env("APP_PORT", "5000")),
        "DATABASE_URL": env("DATABASE_URL") or DEFAULT_SQLITE,
        "API_KEYS": _split(env("API_KEYS")),
        "ADMIN_API_KEYS": _split(env("ADMIN_API_KEYS")),
        "CACHE_ENABLED": _flag(env("CACHE_ENABLED"), True),
        "CACHE_TTL_SECONDS": int(env("CACHE_TTL_SECONDS", "300")),
        "CACHE_MAX_ENTRIES": int(env("CACHE_MAX_ENTRIES", "1024")),
        "LOG_DIR": str(ROOT / (env("LOG_DIR") or "logs")),     # relative paths count from the project root
        "LOG_LEVEL": env("LOG_LEVEL", "INFO").upper(),
        "MAX_CONTENT_LENGTH": 1 * 1024 * 1024,   # reject request bodies over 1 MB
        "MAX_BATCH_SIZE": 100,                   # max materials per /predict request
        "MAX_TOP_N": 20,                         # max recommendations per /recommend request
        "JSON_SORT_KEYS": False,
    }
