"""
EcoPackAI - Flask API
Module: Model Serving & API Layer

Entry point of the API. create_app() wires together:
    settings     backend/settings.py         (environment variables / .env)
    logging      backend/logging_setup.py     (config/logging.yaml -> logs/app.log, logs/security.log)
    database     backend/db/                  (SQLAlchemy; PostgreSQL or SQLite)
    cache        backend/cache.py             (in-memory TTL + LRU response cache)
    middleware   backend/middleware/          (request IDs, header checks, API-key auth)
    routes       /health /ready /predict /recommend /schema /admin/* /reports/<run_id>.csv|.pdf
    frontend     / and /<page>.html, /static/*   (pages in frontend/)

The ML code itself lives in src/ (predictor and ranking logic).

Run (from the project root):
    python backend/manage.py init-db      # once: create tables + load the CSVs
    python backend/app.py
"""

import sys
import time
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, abort, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "src", ROOT / "backend"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from cache import ResponseCache  # noqa: E402
from db import Database  # noqa: E402
from logging_setup import app_log, security_log, setup_logging  # noqa: E402
from middleware import request_context  # noqa: E402
from models import Material  # noqa: E402
from routes.admin import admin_bp  # noqa: E402
from routes.predict import predict_bp  # noqa: E402
from routes.recommend import recommend_bp  # noqa: E402
from routes.reports import reports_bp  # noqa: E402
from services import PredictionService  # noqa: E402
from settings import load_settings  # noqa: E402

FRONTEND = ROOT / "frontend"
PAGES = {"index.html", "predict.html", "results.html", "dashboard.html"}

SERVICE_NAME = "ecopackai-api"
API_VERSION = "1.1.0"


def create_app(test_config=None) -> Flask:
    """Build and configure the Flask app (also used by the tests)."""
    # The frontend (frontend/) is served by the same server, so pages call the API without CORS
    app = Flask(__name__, static_folder=str(FRONTEND / "static"), static_url_path="/static")
    app.config.update(load_settings())
    if test_config:
        app.config.update(test_config)
    app.config["STARTED_AT"] = time.time()

    setup_logging(app.config["LOG_DIR"], app.config["LOG_LEVEL"])
    if not (app.config["API_KEYS"] or app.config["ADMIN_API_KEYS"]):
        if app.config["ENV_NAME"] == "production":
            raise RuntimeError("API_KEYS / ADMIN_API_KEYS must be set when APP_ENV=production")
        security_log.warning("No API keys configured: authentication is OFF (development only)",
                             extra={"event": "auth_disabled"})

    db = Database(app.config["DATABASE_URL"])
    app.extensions["ecopackai"] = SimpleNamespace(
        db=db,
        cache=ResponseCache(app.config["CACHE_TTL_SECONDS"], app.config["CACHE_MAX_ENTRIES"],
                            app.config["CACHE_ENABLED"]),
        service=PredictionService(db),
    )

    request_context.register(app)
    app.register_blueprint(predict_bp)
    app.register_blueprint(recommend_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reports_bp)

    @app.get("/")
    def home_page():
        return send_from_directory(FRONTEND, "index.html")

    @app.get("/<name>.html")
    def frontend_page(name):
        """Only the four known pages; anything else is a JSON 404."""
        page = f"{name}.html"
        if page not in PAGES:
            abort(404)
        return send_from_directory(FRONTEND, page)

    @app.get("/health")
    def health():
        """Liveness check: answers instantly; never loads the models or touches the database."""
        return jsonify({
            "status": "ok",
            "service": SERVICE_NAME,
            "version": API_VERSION,
            "environment": app.config["ENV_NAME"],
            "uptime_seconds": round(time.time() - app.config["STARTED_AT"], 1),
            "models_loaded": app.extensions["ecopackai"].service.is_loaded,
        })

    @app.get("/ready")
    def ready():
        """Readiness check: database reachable, schema migrated, materials loaded."""
        checks = {}
        try:
            db.ping()
            checks["database"] = "ok"
            checks["schema"] = "ok" if _schema_is_current(db) else "migration needed"
            checks["materials"] = "ok" if db.count(Material) > 0 else "empty"
        except Exception:
            app_log.exception("Readiness check failed", extra={"event": "not_ready"})
            checks.setdefault("database", "unreachable")
        is_ready = all(value == "ok" for value in checks.values()) and len(checks) == 3
        return jsonify({"status": "ready" if is_ready else "not_ready", "checks": checks}), \
            200 if is_ready else 503

    @app.errorhandler(HTTPException)
    def http_error(err):
        """404, 405, 413, ... as JSON instead of HTML pages."""
        from flask import g
        return jsonify({"status": "error", "request_id": g.get("request_id"),
                        "error": {"code": err.name.lower().replace(" ", "_"),
                                  "message": err.description}}), err.code

    @app.errorhandler(Exception)
    def unexpected_error(err):
        """Never leak a stack trace to the client; log it with the request ID instead."""
        from flask import g
        app_log.exception("Unhandled error", extra={"event": "unhandled_error"})
        return jsonify({"status": "error", "request_id": g.get("request_id"),
                        "error": {"code": "internal_error",
                                  "message": "Unexpected server error. Quote the request_id when reporting it."}}), 500

    app_log.info("API started", extra={"event": "startup", "environment": app.config["ENV_NAME"],
                                       "database": db.safe_url, "cache_enabled": app.config["CACHE_ENABLED"]})
    return app


def _schema_is_current(db) -> bool:
    """True if the database is at the latest Alembic migration."""
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from alembic.config import Config

    script = ScriptDirectory.from_config(Config(str(ROOT / "backend" / "alembic.ini")))
    with db.engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    return current == script.get_current_head()


if __name__ == "__main__":
    application = create_app()
    application.run(host=application.config["HOST"], port=application.config["PORT"],
                    debug=application.config["ENV_NAME"] == "development")
