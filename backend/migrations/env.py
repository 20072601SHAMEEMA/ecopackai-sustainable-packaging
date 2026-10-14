"""
Alembic environment for EcoPackAI.

Uses the ORM models in backend/models as the target schema and takes the
database URL from (in order) the 'sqlalchemy.url' option set by manage.py,
or DATABASE_URL via backend/settings.py.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from db import ensure_sqlite_folder  # noqa: E402
from models import Base  # noqa: E402
from settings import load_settings  # noqa: E402

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
url = config.get_main_option("sqlalchemy.url") or load_settings()["DATABASE_URL"]


def run_migrations_offline():
    """Write the SQL to stdout instead of running it (alembic upgrade head --sql)."""
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, render_as_batch=url.startswith("sqlite"))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    ensure_sqlite_folder(url)
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=connection.dialect.name == "sqlite", compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
