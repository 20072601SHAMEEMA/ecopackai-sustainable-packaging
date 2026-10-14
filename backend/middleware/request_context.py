"""
EcoPackAI - Request Context Middleware
Module: Flask Backend - Security & Observability

Runs around every request:
    before  - assign a request ID (reuse a valid incoming X-Request-ID)
            - reject POST/PUT/PATCH bodies that are not JSON (415)
            - reject malformed X-Request-ID headers (400)
    after   - add X-Request-ID and basic security headers to the response
            - write one access-log line: method, path, status, duration, role
"""

import re
import time
import uuid

from flask import g, jsonify, request

from logging_setup import access_log, security_log

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
BODY_METHODS = {"POST", "PUT", "PATCH"}


def _error(status: int, code: str, message: str):
    return jsonify({"status": "error", "request_id": g.request_id,
                    "error": {"code": code, "message": message}}), status


def register(app):
    @app.before_request
    def start_request():
        g.started = time.perf_counter()
        incoming = request.headers.get("X-Request-ID")
        if incoming is not None and not REQUEST_ID_PATTERN.match(incoming):
            g.request_id = uuid.uuid4().hex[:12]
            security_log.warning("Malformed X-Request-ID header rejected", extra={
                "event": "bad_header", "header": "X-Request-ID", "path": request.path,
                "remote_addr": request.remote_addr})
            return _error(400, "bad_request", "X-Request-ID must be 8-64 letters, digits, '.', '_' or '-'.")
        g.request_id = incoming or uuid.uuid4().hex[:12]

        if request.method in BODY_METHODS and request.content_length and not request.is_json:
            return _error(415, "unsupported_media_type", "Send JSON with 'Content-Type: application/json'.")
        return None

    @app.after_request
    def finish_request(response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        duration_ms = round((time.perf_counter() - g.get("started", time.perf_counter())) * 1000, 2)
        level = 40 if response.status_code >= 500 else 30 if response.status_code >= 400 else 20
        access_log.log(level, f"{request.method} {request.path} {response.status_code}", extra={
            "event": "request", "method": request.method, "path": request.path,
            "status": response.status_code, "duration_ms": duration_ms,
            "remote_addr": request.remote_addr, "auth_role": g.get("auth_role"),
            "key_fingerprint": g.get("key_fingerprint"), "cache": response.headers.get("X-Cache"),
        })
        return response
