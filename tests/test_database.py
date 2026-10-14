"""
EcoPackAI - Database Tests (integration)
Module: Flask Backend - Data Persistence

Migrations, table mapping, relationships, constraints, seeding, and that
the schema matches the processed data and the generated documentation.
Runs on SQLite by default and on PostgreSQL when TEST_DATABASE_URL is set.

Run with: pytest tests/test_database.py -v
"""

import pandas as pd
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from conftest import ROOT
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from db import Database
from db.seed import seed
from manage import data_dictionary, export_schema
from models import Base, Material, Product, RecommendationLog, RecommendationRun

TABLES = {"materials", "products", "recommendation_runs", "recommendation_logs", "prediction_history"}


def alembic_config(url):
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["configure_logging"] = False
    return config


# ---- Connectivity and tables ----

def test_database_is_reachable(db):
    db.ping()


def test_all_tables_exist(db):
    assert TABLES <= set(inspect(db.engine).get_table_names())


def test_database_matches_the_models(db):
    """The migrated schema is exactly what the ORM models describe (no missing migration)."""
    with db.engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert differences == []


def test_seeded_row_counts(db):
    assert db.count(Material) == 403 and db.count(Product) == 1500


def test_seed_is_idempotent(db):
    assert seed(db) == {"materials": 0, "products": 0}


# ---- Consistency with data and documentation ----

def test_table_columns_match_processed_csvs():
    for model, name in ((Material, "materials.csv"), (Product, "products.csv")):
        csv_columns = list(pd.read_csv(ROOT / "data" / "processed" / name, nrows=1).columns)
        assert [c.name for c in model.__table__.columns] == csv_columns


def test_database_values_equal_the_csv(db):
    with db.engine.connect() as connection:
        stored = pd.read_sql_table("materials", connection).sort_values("material_id").reset_index(drop=True)
    stored.columns = [f"{c}" for c in stored.columns]
    expected = pd.read_csv(ROOT / "data" / "processed" / "materials.csv")
    pd.testing.assert_frame_equal(stored[expected.columns], expected, check_dtype=False)


def test_every_column_is_documented():
    for table in Base.metadata.sorted_tables:
        assert table.comment
        assert all(column.comment for column in table.columns), table.name


def test_generated_docs_are_up_to_date():
    assert (ROOT / "docs" / "data_dictionary.md").read_text(encoding="utf-8") == data_dictionary(), \
        "Re-run: python backend/manage.py data-dictionary"
    assert (ROOT / "backend" / "db" / "schema.sql").read_text(encoding="utf-8") == export_schema(), \
        "Re-run: python backend/manage.py export-schema"


# ---- Relationships and constraints ----

def test_product_material_relationship(db):
    with db.session() as session:
        run = RecommendationRun(request_id="rel-test-0001", product_id=10, product_snapshot={"category": "Food"},
                                mode="balanced", top_n=1, n_candidates=1, status="ok",
                                cost_model_version="test", co2_model_version="test")
        run.results = [RecommendationLog(product_id=10, recommended_material_id="MAT_0154", cost_prediction=2.8,
                                         co2_prediction=0.5, final_score=80.0, material_rank=1)]
        session.add(run)
        session.flush()
        product = session.get(Product, 10)
        material = session.get(Material, "MAT_0154")
        assert run.results[0].product is product and run.results[0].material is material
        assert run in product.runs
        assert any(log.run_id == run.run_id for log in product.recommendations)
        assert any(log.run_id == run.run_id for log in material.recommendations)
        session.rollback()


def test_unknown_material_is_rejected_by_foreign_key(db):
    with pytest.raises(IntegrityError):
        with db.session() as session:
            run = RecommendationRun(request_id="fk-test-0001", product_snapshot={}, mode="balanced", top_n=1,
                                    n_candidates=1, status="ok", cost_model_version="t", co2_model_version="t")
            run.results = [RecommendationLog(recommended_material_id="MAT_9999", cost_prediction=1,
                                             co2_prediction=1, final_score=1, material_rank=1)]
            session.add(run)


def test_deleting_a_run_deletes_its_results(db):
    with db.session() as session:
        run = RecommendationRun(request_id="cascade-0001", product_snapshot={}, mode="balanced", top_n=1,
                                n_candidates=1, status="ok", cost_model_version="t", co2_model_version="t")
        run.results = [RecommendationLog(recommended_material_id="MAT_0001", cost_prediction=1,
                                         co2_prediction=1, final_score=1, material_rank=1)]
        session.add(run)
    with db.engine.begin() as connection:
        connection.execute(RecommendationRun.__table__.delete().where(RecommendationRun.request_id == "cascade-0001"))
    with db.session() as session:
        left = session.scalars(select(RecommendationLog).where(RecommendationLog.run_id == run.run_id)).all()
    assert left == []


def test_created_at_is_filled_by_the_database(db):
    with db.session() as session:
        run = RecommendationRun(request_id="time-test-0001", product_snapshot={}, mode="balanced", top_n=1,
                                n_candidates=0, status="no_valid_material", cost_model_version="t",
                                co2_model_version="t")
        session.add(run)
        session.flush()
        session.refresh(run)
        assert run.created_at is not None
        session.rollback()


# ---- Migrations ----

def test_init_db_creates_a_missing_database_folder(tmp_path):
    """First run on a fresh checkout: the instance/ folder does not exist yet."""
    from manage import migrate
    url = f"sqlite:///{(tmp_path / 'not_created_yet' / 'ecopackai.db').as_posix()}"
    migrate(url)
    fresh = Database(url)
    assert TABLES <= set(inspect(fresh.engine).get_table_names())
    fresh.engine.dispose()


def test_migrations_upgrade_and_downgrade_on_a_fresh_database(tmp_path):
    url = f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    config = alembic_config(url)
    command.upgrade(config, "head")
    fresh = Database(url)
    assert TABLES <= set(inspect(fresh.engine).get_table_names())
    command.downgrade(config, "base")
    assert set(inspect(fresh.engine).get_table_names()) <= {"alembic_version"}
    command.upgrade(config, "head")
    assert seed(fresh) == {"materials": 403, "products": 1500}
    fresh.engine.dispose()
