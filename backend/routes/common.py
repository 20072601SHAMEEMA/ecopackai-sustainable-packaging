"""
EcoPackAI - Shared Route Helpers
Module: Flask Backend

Access to the per-app components (database, cache, model service) and the
common JSON error / model-info formats used by every endpoint.
"""

from flask import current_app, g, jsonify, request


def components():
    """The app's database, cache and model service (created in create_app)."""
    return current_app.extensions["ecopackai"]


def error(status: int, code: str, message: str, details=None):
    payload = {"status": "error", "request_id": g.get("request_id"),
               "error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status


def json_body():
    """Return (body, None) or (None, error_response) for a JSON request body."""
    if not request.is_json:
        return None, error(415, "unsupported_media_type", "Send JSON with 'Content-Type: application/json'.")
    body = request.get_json(silent=True)
    if body is None:
        return None, error(400, "invalid_json", "The request body is not valid JSON.")
    return body, None


def model_info(metadata: dict) -> dict:
    info = {"package_version": metadata["package_version"]}
    for key, model in metadata["models"].items():
        info[key] = {"name": model["model_name"], "version": model["model_version"],
                     "target": model["target_variable"], "unit": model["unit"]}
    return info
