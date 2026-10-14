"""
Shared test setup for the EcoPackAI backend.

Database used by the API and database tests:
    - default: a fresh SQLite file in a temporary folder (no server needed)
    - TEST_DATABASE_URL=postgresql://...: that PostgreSQL database instead
      (CI runs both). It is reset to an empty schema, migrated and seeded.
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "backend", ROOT / "src"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

CLIENT_KEY = "test-client-key-0001"
ADMIN_KEY = "test-admin-key-0001"
CLIENT = {"X-API-Key": CLIENT_KEY}
ADMIN = {"X-API-Key": ADMIN_KEY}
MATERIALS = pd.read_csv(ROOT / "data" / "processed" / "materials.csv")
PRODUCT = {"product_id": 1, "category": "Food", "product_weight_kg": 0.5,
           "fragility_index": 2, "shipping_type": "Road"}


def material(i=0, **changes):
    """A real catalogue row as a JSON-ready dict."""
    row = json.loads(MATERIALS.iloc[[i]].to_json(orient="records"))[0]
    row.update(changes)
    return row


def migrate_fresh(url: str):
    """Empty the database, apply all migrations and load the CSVs."""
    from alembic import command
    from alembic.config import Config

    from db import Database
    from db.seed import seed

    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["configure_logging"] = False
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    seed(Database(url))


@pytest.fixture(scope="session")
def database_url(tmp_path_factory):
    url = os.environ.get("TEST_DATABASE_URL") or \
        f"sqlite:///{(tmp_path_factory.mktemp('db') / 'test.db').as_posix()}"
    migrate_fresh(url)
    return url


@pytest.fixture(scope="session")
def make_app(database_url, tmp_path_factory):
    """Factory for apps with test keys, the test database and a private log folder."""
    from app import create_app

    def factory(**overrides):
        config = {"TESTING": True, "DATABASE_URL": database_url, "API_KEYS": (CLIENT_KEY,),
                  "ADMIN_API_KEYS": (ADMIN_KEY,), "LOG_DIR": str(tmp_path_factory.mktemp("logs")),
                  "CACHE_ENABLED": True}
        config.update(overrides)
        return create_app(config)
    return factory


@pytest.fixture(scope="session")
def app(make_app):
    return make_app()


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return app.extensions["ecopackai"].db
