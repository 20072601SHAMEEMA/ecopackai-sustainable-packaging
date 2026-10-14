"""
EcoPackAI - Local PostgreSQL for Development
Module: Flask Backend - Data Persistence

Starts a real PostgreSQL server from the 'pgserver' pip package (no Docker,
no installer, no admin rights). Data is kept in instance/pgdata, and the
server keeps running in the background until you stop it.

Usage (from the project root, needs: pip install -r environments/requirements-dev.txt):
    python scripts/dev_postgres.py          start (or reuse) the server, print DATABASE_URL
    python scripts/dev_postgres.py --stop   stop the server

Then, in the same terminal (Windows cmd / Anaconda Prompt):
    set DATABASE_URL=<the URL printed>
    python backend/manage.py init-db
    python backend/app.py
"""

import argparse
from pathlib import Path

import pgserver
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "instance" / "pgdata"
DATABASE = "ecopackai"


def main():
    parser = argparse.ArgumentParser(description="Local PostgreSQL for EcoPackAI development")
    parser.add_argument("--stop", action="store_true", help="stop the server")
    args = parser.parse_args()

    if args.stop:
        pgserver.get_server(DATA_DIR, cleanup_mode="stop").cleanup()
        print("PostgreSQL stopped.")
        return

    DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
    server = pgserver.get_server(DATA_DIR, cleanup_mode=None)       # keeps running after this script ends
    admin_url = server.get_uri()
    engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        exists = connection.execute(sa.text("SELECT 1 FROM pg_database WHERE datname = :name"),
                                    {"name": DATABASE}).scalar()
        if not exists:
            connection.execute(sa.text(f"CREATE DATABASE {DATABASE}"))
    engine.dispose()

    url = admin_url.rsplit("/", 1)[0] + f"/{DATABASE}"
    print("PostgreSQL is running.\n")
    print(f"  set DATABASE_URL={url}\n")
    print("Then: python backend/manage.py init-db   and   python backend/app.py")
    print("Stop it later with: python scripts/dev_postgres.py --stop")


if __name__ == "__main__":
    main()
