"""
EcoPackAI - Admin Endpoints
Module: Flask Backend - Security

Restricted to admin API keys (ADMIN_API_KEYS); client keys get 403.

GET  /admin/stats         cache statistics, row counts, model and database info
POST /admin/cache/clear   empty the response cache (e.g. after editing the database)
"""

import time

from flask import Blueprint, current_app, jsonify

from logging_setup import security_log
from middleware.auth import require_auth
from models import ALL_MODELS
from routes.common import components, error

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/stats")
@require_auth("admin")
def stats():
    parts = components()
    try:
        rows = {model.__tablename__: parts.db.count(model) for model in ALL_MODELS}
    except Exception:
        return error(503, "database_unavailable", "The database is not reachable.")
    service = parts.service
    return jsonify({
        "status": "success",
        "uptime_seconds": round(time.time() - current_app.config["STARTED_AT"], 1),
        "database": {"backend": parts.db.backend, "url": parts.db.safe_url, "rows": rows},
        "cache": parts.cache.stats(),
        "models": {"loaded": service.is_loaded,
                   "versions": service.model_versions() if service.is_loaded else None,
                   "catalogue_source": service.catalogue_source},
    })


@admin_bp.post("/cache/clear")
@require_auth("admin")
def clear_cache():
    removed = components().cache.clear()
    security_log.info("Response cache cleared", extra={"event": "cache_cleared", "entries_removed": removed})
    return jsonify({"status": "success", "entries_removed": removed})
