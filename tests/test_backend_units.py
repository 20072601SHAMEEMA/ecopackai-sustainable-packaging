"""
EcoPackAI - Backend Unit Tests
Module: Flask Backend - Quality Assurance

Small, fast tests of single components, without the database or models:
cache, cache keys, authentication helpers, log formatting, settings,
and request validation functions.

Run with: pytest tests/test_backend_units.py -v
"""

import json
import logging

import pytest
from conftest import PRODUCT, material
from flask import Flask

from cache import ResponseCache, make_key
from logging_setup import JsonFormatter
from middleware.auth import fingerprint, presented_key, role_of
from recommendation.ranker import load_config
from routes.predict import CONFIG_FILE, validate_request
from routes.recommend import validate_recommend
from settings import _flag, _split

CONFIG = load_config(CONFIG_FILE)


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


# ---- ResponseCache ----

def test_cache_returns_what_was_stored():
    cache = ResponseCache()
    cache.set("k", {"a": [1, 2]})
    assert cache.get("k") == {"a": [1, 2]} and cache.get("other") is None


def test_cache_entries_expire_after_ttl():
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=60, clock=clock)
    cache.set("k", "v")
    clock.now += 59
    assert cache.get("k") == "v"
    clock.now += 2
    assert cache.get("k") is None and cache.stats()["expirations"] == 1


def test_cache_evicts_least_recently_used():
    cache = ResponseCache(max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")                 # 'a' is now the most recently used
    cache.set("c", 3)              # so 'b' is evicted
    assert cache.get("b") is None and cache.get("a") == 1 and cache.get("c") == 3
    assert cache.stats()["evictions"] == 1


def test_cached_values_cannot_be_changed_from_outside():
    cache = ResponseCache()
    value = {"warnings": []}
    cache.set("k", value)
    value["warnings"].append("changed after set")
    cache.get("k")["warnings"].append("changed after get")
    assert cache.get("k") == {"warnings": []}


def test_disabled_cache_stores_nothing():
    cache = ResponseCache(enabled=False)
    cache.set("k", 1)
    assert cache.get("k") is None and cache.stats()["entries"] == 0


def test_cache_stats_and_clear():
    cache = ResponseCache()
    cache.set("k", 1)
    cache.get("k")
    cache.get("missing")
    stats = cache.stats()
    assert (stats["hits"], stats["misses"], stats["hit_rate"]) == (1, 1, 0.5)
    assert cache.clear() == 1 and cache.stats()["entries"] == 0


# ---- Cache keys ----

def test_cache_key_ignores_json_key_order():
    assert make_key("/predict", {"a": 1, "b": 2}, "m") == make_key("/predict", {"b": 2, "a": 1}, "m")


def test_cache_key_changes_with_body_endpoint_and_fingerprints():
    base = make_key("/predict", {"a": 1}, "model-v1", "config-v1")
    assert base != make_key("/predict", {"a": 2}, "model-v1", "config-v1")
    assert base != make_key("/recommend", {"a": 1}, "model-v1", "config-v1")
    assert base != make_key("/predict", {"a": 1}, "model-v2", "config-v1")       # retrained model
    assert base != make_key("/predict", {"a": 1}, "model-v1", "config-v2")       # changed config


# ---- Authentication helpers ----

@pytest.fixture
def auth_app():
    app = Flask(__name__)
    app.config.update(API_KEYS=("client-1", "client-2"), ADMIN_API_KEYS=("admin-1",))
    return app


@pytest.mark.parametrize("headers, expected", [
    ({"X-API-Key": "abc"}, "abc"),
    ({"Authorization": "Bearer abc"}, "abc"),
    ({"Authorization": "bearer   abc "}, "abc"),
    ({"Authorization": "Basic abc"}, None),
    ({"Authorization": "Bearer "}, None),
    ({}, None),
])
def test_presented_key(auth_app, headers, expected):
    with auth_app.test_request_context(headers=headers):
        assert presented_key() == expected


def test_role_of(auth_app):
    with auth_app.test_request_context():
        assert role_of("client-2") == "client"
        assert role_of("admin-1") == "admin"
        assert role_of("client-") is None and role_of("") is None


def test_fingerprint_is_short_and_not_the_key():
    assert len(fingerprint("secret-key")) == 8 and "secret" not in fingerprint("secret-key")


# ---- Logging ----

def test_json_formatter_fields():
    record = logging.LogRecord("ecopackai", logging.INFO, __file__, 1, "Prediction served", None, None)
    record.request_id = "abc123"
    record.event = "prediction"
    line = json.loads(JsonFormatter().format(record))
    assert line["level"] == "INFO" and line["logger"] == "ecopackai" and line["message"] == "Prediction served"
    assert line["request_id"] == "abc123" and line["event"] == "prediction"
    assert line["timestamp"].endswith("+00:00")


def test_json_formatter_includes_exception():
    try:
        raise ValueError("bad thing")
    except ValueError:
        import sys
        record = logging.LogRecord("ecopackai", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())
    assert "ValueError: bad thing" in json.loads(JsonFormatter().format(record))["exception"]


# ---- Settings ----

def test_settings_helpers():
    assert _split(" a, b ,,c ") == ("a", "b", "c") and _split(None) == ()
    assert _flag("TRUE", False) is True and _flag("off", True) is False and _flag(None, True) is True


# ---- Validation functions ----

def test_validate_request_accepts_valid_body():
    materials, product, mode, errors = validate_request({"material": material(0)}, CONFIG, 100)
    assert errors == [] and len(materials) == 1 and product is None and mode == CONFIG["default_mode"]


def test_validate_request_rejects_bool_as_number():
    errors = validate_request({"material": material(0, load_handling_score=True)}, CONFIG, 100)[3]
    assert errors and errors[0]["field"] == "material.load_handling_score"


def test_validate_recommend_defaults_and_options():
    product_id, inline, mode, top_n, errors = validate_recommend({"product_id": 5}, CONFIG, 20)
    assert (product_id, inline, mode, top_n, errors) == (5, None, CONFIG["default_mode"], CONFIG["top_n"], [])
    result = validate_recommend({"product": PRODUCT, "options": {"mode": "cost_first", "top_n": 3}}, CONFIG, 20)
    assert result[2:] == ("cost_first", 3, [])


@pytest.mark.parametrize("product_id", [0, -1, True, 1.5, "7"])
def test_validate_recommend_rejects_bad_product_ids(product_id):
    assert validate_recommend({"product_id": product_id}, CONFIG, 20)[4]
