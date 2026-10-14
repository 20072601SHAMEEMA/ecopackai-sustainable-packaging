"""
EcoPackAI - Database Ingestion Script
Module: Data Pipeline / Dataset Ingestion

Loads the cleaned CSVs from data/processed/ into the PostgreSQL
database defined in schema.sql. Run clean_data.py first.

Usage:
    python ingest_data.py

Requires a running PostgreSQL instance matching the connection
details below (see environments/docker-compose.yml for local dev).
"""

import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path

PROCESSED_DIR = Path("data/processed")

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "ecopackai_db"),
    "user": os.getenv("DB_USER", "ecopack_user"),
    "password": os.getenv("DB_PASSWORD", "ecopack_pass"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def ingest_materials(conn):
    df = pd.read_csv(PROCESSED_DIR / "materials.csv")
    columns = list(df.columns)
    values = [tuple(row) for row in df.to_numpy()]

    query = f"""
        INSERT INTO materials ({", ".join(columns)})
        VALUES %s
        ON CONFLICT (material_id) DO NOTHING;
    """
    with conn.cursor() as cur:
        execute_values(cur, query, values)
    conn.commit()
    print(f"Inserted {len(values)} rows into materials (duplicates skipped).")


def ingest_products(conn):
    df = pd.read_csv(PROCESSED_DIR / "products.csv")
    columns = list(df.columns)
    values = [tuple(row) for row in df.to_numpy()]

    query = f"""
        INSERT INTO products ({", ".join(columns)})
        VALUES %s
        ON CONFLICT (product_id) DO NOTHING;
    """
    with conn.cursor() as cur:
        execute_values(cur, query, values)
    conn.commit()
    print(f"Inserted {len(values)} rows into products (duplicates skipped).")


if __name__ == "__main__":
    conn = get_connection()
    try:
        ingest_materials(conn)
        ingest_products(conn)
    finally:
        conn.close()
    print("Ingestion complete.")
