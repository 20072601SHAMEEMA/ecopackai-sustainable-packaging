"""
EcoPackAI - Authentication Middleware
Module: Flask Backend - Security

API-key authentication with two roles:
    client  -> may call /predict and /recommend      (keys in API_KEYS)
    admin   -> may also call /admin/*                 (keys in ADMIN_API_KEYS)

Send the key in either header:
    X-API-Key: <key>
    Authorization: Bearer <key>

Usage on a route:
    @require_auth("client")    or    @require_auth("admin")

401 = no key or unknown key, 403 = valid key without the required role.
Keys are compared in constant time; keys themselves are never logged, only
a short fingerprint (first 8 hex characters of their SHA-256).
"""

import hashlib
import hmac
from functools import wraps

from flask import current_app, g, jsonify, request

from logging_setup import security_log


def fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def presented_key():
    """The key from X-API-Key or 'Authorization: Bearer <key>', or None."""
    key = request.headers.get("X-API-Key", "").strip()
    if key:
        return key
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return None


def _matches(key: str, allowed) -> bool:
    # check every key (no early exit) so timing does not reveal which keys exist
    found = False
    for candidate in allowed:
        found |= hmac.compare_digest(key.encode("utf-8"), candidate.encode("utf-8"))
    return found


def role_of(key: str):
    if _matches(key, current_app.config["ADMIN_API_KEYS"]):
        return "admin"
    if _matches(key, current_app.config["API_KEYS"]):
        return "client"
    return None


def auth_enabled() -> bool:
    return bool(current_app.config["API_KEYS"] or current_app.config["ADMIN_API_KEYS"])


def _deny(status: int, code: str, message: str, reason: str, key=None):
    security_log.warning("Access denied", extra={
        "event": "auth_denied", "reason": reason, "status": status,
        "method": request.method, "path": request.path, "remote_addr": request.remote_addr,
        "key_fingerprint": fingerprint(key) if key else None,
    })
    return jsonify({"status": "error", "request_id": g.get("request_id"),
                    "error": {"code": code, "message": message}}), status


def require_auth(role: str):
    """Decorator: the request must carry a key with the given role ('client' or 'admin')."""
    if role not in {"client", "admin"}:
        raise ValueError(f"Unknown role '{role}'")

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not auth_enabled():            # development without keys (see create_app)
                g.auth_role = "anonymous"
                return view(*args, **kwargs)

            key = presented_key()
            if key is None:
                return _deny(401, "unauthorized", "Missing API key. Send 'X-API-Key: <key>' "
                                                  "or 'Authorization: Bearer <key>'.", "missing_key")
            granted = role_of(key)
            if granted is None:
                return _deny(401, "unauthorized", "Invalid API key.", "invalid_key", key)
            if role == "admin" and granted != "admin":
                return _deny(403, "forbidden", "This endpoint needs an admin key.", "insufficient_role", key)

            g.auth_role = granted
            g.key_fingerprint = fingerprint(key)
            return view(*args, **kwargs)
        return wrapper
    return decorator
