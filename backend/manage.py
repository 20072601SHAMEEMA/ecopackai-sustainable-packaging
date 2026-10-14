"""
EcoPackAI - Management Commands
Module: Flask Backend - Data Persistence

Usage (from the project root):
    python backend/manage.py init-db            create/upgrade all tables (Alembic) and load the CSVs
    python backend/manage.py migrate            create/upgrade all tables only
    python backend/manage.py seed               load data/processed/*.csv into empty tables
    python backend/manage.py export-schema      write backend/db/schema.sql (PostgreSQL DDL)
    python backend/manage.py data-dictionary    write the database section of docs/data_dictionary.md

The database is chosen by DATABASE_URL (default: SQLite file instance/ecopackai.db).
"""

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from db import Database  # noqa: E402
from db.seed import seed  # noqa: E402
from models import Base  # noqa: E402
from settings import load_settings  # noqa: E402

SCHEMA_SQL = BACKEND / "db" / "schema.sql"
DATA_DICTIONARY = ROOT / "docs" / "data_dictionary.md"


def migrate(url: str) -> None:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["configure_logging"] = False
    command.upgrade(config, "head")


def export_schema() -> str:
    """PostgreSQL DDL generated from the ORM models (reference copy of the schema)."""
    dialect = postgresql.dialect()
    parts = ["-- EcoPackAI database schema (PostgreSQL)",
             "-- GENERATED from backend/models by: python backend/manage.py export-schema",
             "-- Do not edit by hand. Tables are created by the Alembic migrations in backend/migrations/.",
             ""]
    for table in Base.metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
        for index in sorted(table.indexes, key=lambda i: i.name):
            parts.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";")
        parts.append("")
    return "\n".join(parts)


def data_dictionary() -> str:
    lines = ["# Data Dictionary — EcoPackAI Database",
             "",
             "GENERATED from the ORM models in `backend/models/` by "
             "`python backend/manage.py data-dictionary`. Do not edit by hand.",
             "Column names match `data/processed/materials.csv` and `products.csv`; "
             "the dataset-level dictionary (encoded/engineered columns) is `docs/data_dictionary_v2.xlsx`.",
             "",
             "| Table | Purpose |", "|---|---|"]
    lines += [f"| `{t.name}` | {t.comment} |" for t in Base.metadata.sorted_tables]
    for table in Base.metadata.sorted_tables:
        lines += ["", f"## Table: {table.name}", "", table.comment or "", "",
                  "| Column | Type | Nullable | Key | Description |", "|---|---|---|---|---|"]
        for column in table.columns:
            keys = []
            if column.primary_key:
                keys.append("PK")
            keys += [f"FK → {fk.target_fullname}" for fk in column.foreign_keys]
            if column.index:
                keys.append("indexed")
            column_type = column.type.compile(dialect=postgresql.dialect())
            lines.append(f"| {column.name} | {column_type} | {'yes' if column.nullable else 'no'} | "
                         f"{', '.join(keys)} | {column.comment or ''} |")
    lines += ["", "## Relationships", "",
              "- `recommendation_runs.product_id` → `products` (NULL when the product was sent inline)",
              "- `recommendation_logs.run_id` → `recommendation_runs` (one run has many ranked materials; "
              "deleting a run deletes its rows)",
              "- `recommendation_logs.product_id` → `products` and `recommendation_logs.recommended_material_id` "
              "→ `materials`: this table is the many-to-many link between products and materials",
              "- `prediction_history` stores what clients sent, which may be new materials, so it has no "
              "foreign key to `materials`", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="EcoPackAI database management")
    parser.add_argument("command", choices=["init-db", "migrate", "seed", "export-schema", "data-dictionary"])
    args = parser.parse_args()
    url = load_settings()["DATABASE_URL"]

    if args.command in {"init-db", "migrate"}:
        migrate(url)
        print(f"Schema is at the latest migration ({Database(url).safe_url})")
    if args.command in {"init-db", "seed"}:
        added = seed(Database(url))
        print("Rows added: " + ", ".join(f"{table} {count}" for table, count in added.items())
              + "  (tables that already had rows are left unchanged)")
    if args.command == "export-schema":
        SCHEMA_SQL.write_text(export_schema(), encoding="utf-8")
        print(f"Wrote {SCHEMA_SQL.relative_to(ROOT)}")
    if args.command == "data-dictionary":
        DATA_DICTIONARY.write_text(data_dictionary(), encoding="utf-8")
        print(f"Wrote {DATA_DICTIONARY.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
