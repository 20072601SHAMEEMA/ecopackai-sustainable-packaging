"""
EcoPackAI - Database Connection
Module: Flask Backend - Data Persistence

One Database object per app: an SQLAlchemy engine plus a session factory.
Works with PostgreSQL (production, docker-compose) and SQLite (local
development and tests) through the same code.
"""

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


def ensure_sqlite_folder(url: str) -> None:
    """SQLite creates the database file but not its folder (e.g. instance/), so create it."""
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite" and parsed.database and parsed.database != ":memory:":
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)


class Database:
    def __init__(self, url: str):
        self.url = url
        parsed = make_url(url)
        options = {"pool_pre_ping": True}          # reconnect if the DB restarted
        ensure_sqlite_folder(url)
        if parsed.get_backend_name() == "sqlite":
            options["connect_args"] = {"check_same_thread": False}
        self.engine = create_engine(url, **options)
        if parsed.get_backend_name() == "sqlite":
            event.listen(self.engine, "connect", _sqlite_enforce_foreign_keys)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    @property
    def backend(self) -> str:
        return self.engine.dialect.name

    @property
    def safe_url(self) -> str:
        """URL with the password hidden, safe for logs and /admin/stats."""
        return make_url(self.url).render_as_string(hide_password=True)

    @contextmanager
    def session(self):
        """Session that commits on success and rolls back on any error."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ping(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def count(self, model) -> int:
        with self.session() as session:
            return session.scalar(select(func.count()).select_from(model))


def _sqlite_enforce_foreign_keys(dbapi_connection, _record):
    """SQLite ignores foreign keys unless this is switched on per connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
