"""
EcoPackAI - Seed the Database
Module: Flask Backend - Data Persistence

Loads data/processed/materials.csv and products.csv into the materials and
products tables. Safe to run repeatedly: a table that already has rows is
left untouched. Run through:  python backend/manage.py seed
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import insert, text

from models import Material, Product

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    Material: ROOT / "data" / "processed" / "materials.csv",
    Product: ROOT / "data" / "processed" / "products.csv",
}


def seed(db) -> dict:
    """Insert the CSV rows into empty tables; return rows added per table."""
    added = {}
    for model, path in SOURCES.items():
        table = model.__tablename__
        if db.count(model) > 0:
            added[table] = 0
            continue
        frame = pd.read_csv(path)
        expected = {c.name for c in model.__table__.columns}
        if set(frame.columns) != expected:
            raise ValueError(f"{path.name} columns do not match table '{table}': "
                             f"missing {sorted(expected - set(frame.columns))}, "
                             f"extra {sorted(set(frame.columns) - expected)}")
        records = frame.astype(object).where(frame.notna(), None).to_dict("records")
        with db.session() as session:
            session.execute(insert(model), records)
            if model is Product and db.backend == "postgresql":
                # IDs came from the CSV, so move the auto-increment counter past them
                session.execute(text("SELECT setval(pg_get_serial_sequence('products', 'product_id'), "
                                     "(SELECT MAX(product_id) FROM products))"))
        added[table] = len(records)
    return added
