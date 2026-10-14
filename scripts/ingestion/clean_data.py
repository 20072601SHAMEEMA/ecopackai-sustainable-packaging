"""
EcoPackAI - Data Cleaning & Validation Script
Module: Data Pipeline / Dataset Ingestion

Reads raw CSVs, validates and cleans them, and writes ingest-ready
versions to data/processed/. Run this before ingest_data.py.
"""

import pandas as pd
import re
from pathlib import Path

RAW_DIR = Path("data/raw_datasets")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def to_snake_case(col: str) -> str:
    """Convert a raw column header like 'Cost per Unit (USD)' into
    a clean snake_case DB column name like 'cost_per_unit_usd'."""
    col = col.strip()
    col = col.replace("%", "percent")
    col = re.sub(r"[()/]", " ", col)          # drop punctuation
    col = re.sub(r"[^a-zA-Z0-9\s]", "", col)  # drop anything else non-alnum
    col = re.sub(r"\s+", "_", col.strip())
    return col.lower()


def clean_materials(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    report = {"rows_before": len(df)}

    # 1. standardize column names to snake_case
    df.columns = [to_snake_case(c) for c in df.columns]

    # 2. rename a couple of columns to match schema.sql exactly
    #    (snake_case auto-conversion is close but not identical)
    rename_map = {
        "co2_emission_per_kg_estimated": "co2_emission_per_kg",
        "carbon_footprint_kg_co2_unit": "carbon_footprint_kg_co2_per_unit",
        "endoflife_disposal_percent": "end_of_life_disposal_percent",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # 3. drop fully/partially incomplete trailing rows
    #    (source file had 1 row with a broken/missing tail of values)
    incomplete_mask = df.isnull().any(axis=1)
    report["incomplete_rows_dropped"] = int(incomplete_mask.sum())
    df = df[~incomplete_mask].reset_index(drop=True)

    # 4. duplicate check on primary key
    report["duplicate_material_ids"] = int(df["material_id"].duplicated().sum())
    df = df.drop_duplicates(subset="material_id").reset_index(drop=True)

    report["rows_after"] = len(df)
    return df, report


def clean_products(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    report = {"rows_before": len(df)}

    # 1. category column had inconsistent values, e.g. " Cosmetics" vs "Cosmetics"
    before_unique = df["category"].nunique()
    df["category"] = df["category"].str.strip()
    after_unique = df["category"].nunique()
    report["category_values_merged"] = before_unique - after_unique

    # 2. duplicate check
    report["duplicate_product_ids"] = int(df["product_id"].duplicated().sum())
    df = df.drop_duplicates(subset="product_id").reset_index(drop=True)

    # 3. null check (none found originally, kept as a safety net)
    report["nulls_found"] = int(df.isnull().sum().sum())
    df = df.dropna().reset_index(drop=True)

    report["rows_after"] = len(df)
    return df, report


if __name__ == "__main__":
    materials_df, materials_report = clean_materials(
        RAW_DIR / "EcoPackAI_dataset.csv"
    )
    products_df, products_report = clean_products(
        RAW_DIR / "product_dataset.csv"
    )

    materials_df.to_csv(PROCESSED_DIR / "materials.csv", index=False)
    products_df.to_csv(PROCESSED_DIR / "products.csv", index=False)

    print("=== Materials cleaning report ===")
    for k, v in materials_report.items():
        print(f"  {k}: {v}")

    print("\n=== Products cleaning report ===")
    for k, v in products_report.items():
        print(f"  {k}: {v}")

    print(f"\nCleaned files written to: {PROCESSED_DIR}/")
