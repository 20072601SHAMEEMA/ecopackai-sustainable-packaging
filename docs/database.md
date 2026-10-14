# Database Integration — EcoPackAI

| Part | File |
|---|---|
| ORM models (SQLAlchemy 2.0) | `backend/models/__init__.py` |
| Connection and sessions | `backend/db/__init__.py` |
| Loading the CSVs | `backend/db/seed.py` |
| Migrations (Alembic) | `backend/alembic.ini`, `backend/migrations/versions/0001_initial_schema.py` |
| Commands | `backend/manage.py` |
| Generated reference docs | `backend/db/schema.sql`, `docs/data_dictionary.md` |
| Tests | `tests/test_database.py` (plus persistence tests in `tests/test_api.py`) |

## 1. Which Database

The same code runs on two databases; `DATABASE_URL` chooses:

| Use | `DATABASE_URL` |
|---|---|
| Production / docker-compose | `postgresql://ecopack_user:ecopack_pass@db:5432/ecopackai_db` |
| Local PostgreSQL without Docker | printed by `python scripts/dev_postgres.py` |
| Default (nothing set) | SQLite file `instance/ecopackai.db` |

SQLite needs no server and is used for quick local work and the default test run.
Everything was also tested on a real PostgreSQL 16 server (162 tests pass on both).

## 2. Tables

Five tables, generated documentation in `docs/data_dictionary.md`:

| Table | Rows come from | Purpose |
|---|---|---|
| `materials` | `data/processed/materials.csv` (403) | Material catalogue; the API ranks these |
| `products` | `data/processed/products.csv` (1,500) | Products; `/recommend` accepts a `product_id` |
| `recommendation_runs` | every `/recommend` call | Product, mode, top N, model versions, cached flag |
| `recommendation_logs` | every `/recommend` call | One row per recommended material, with rank, score and predictions |
| `prediction_history` | every `/predict` call | One row per predicted material: inputs, outputs, model versions |

### Relationships

```
products 1 ──── * recommendation_runs 1 ──── * recommendation_logs * ──── 1 materials
    1 ─────────────────────────────────────────── *
```

- `recommendation_logs` is the link table between products and materials: each row says
  "for this product, this material was recommended at this rank".
- `recommendation_runs` groups the rows of one request; deleting a run deletes its rows
  (`ON DELETE CASCADE`).
- A product sent inline (not from the table) is stored as a JSON snapshot with
  `product_id = NULL`, so no fake product rows are created.
- `prediction_history` has no foreign key to `materials`: clients may send new materials
  that are not in the catalogue.

In Python the relationships are navigable: `run.results`, `run.product`,
`product.recommendations`, `material.recommendations`.

## 3. Consistency With the Data and the Data Dictionary

- `materials` and `products` have exactly the columns of the processed CSVs, in the same
  order, with the same names as the previous hand-written `schema.sql` (v2). A test checks
  the column lists, and another checks that the values read back from the database equal
  the CSVs.
- Every table and column has a description (`comment=`), stored in PostgreSQL too.
- `docs/data_dictionary.md` and `backend/db/schema.sql` are **generated** from the models
  (`python backend/manage.py data-dictionary` / `export-schema`), and a test fails if
  either is out of date, so code and documentation cannot drift apart again.
- The previous `docs/data_dictionary.md` described an early generic schema
  (`strength_mpa`, `weight_capacity`, ...) that never matched the real data. It is kept as
  `archive/data_dictionary_db_v1_generic.md`; the hand-written schema is kept as
  `archive/schema_v2_handwritten.sql`.
- Changes from the hand-written v2 schema: columns are `NOT NULL` (the cleaned data has no
  gaps), `recommendation_logs` gains `run_id` and `final_score`, and
  `recommendation_runs` / `prediction_history` are new.

## 4. Migrations (Version Control of the Schema)

Alembic records every schema change as a numbered migration file in
`backend/migrations/versions/`, and the table `alembic_version` stores which one a
database is at.

```bash
python backend/manage.py init-db     # upgrade to the latest migration + load CSVs (safe to repeat)
python backend/manage.py migrate     # upgrade only
```

After changing a model in `backend/models/`:

```bash
python -m alembic -c backend/alembic.ini revision --autogenerate -m "describe the change"
```

Review the new file, then run `migrate`, `export-schema` and `data-dictionary`.

Tests check that the migrated database matches the models exactly (no forgotten
migration) and that upgrade → downgrade → upgrade works on a fresh database.

`0001_initial_schema.py` was generated with Alembic autogenerate against PostgreSQL and
reviewed. One fix was applied: the timestamp default `now()` was replaced by
`sa.func.now()`, because SQLite has no `now()` function.

## 5. Seeding

`python backend/manage.py seed` (also part of `init-db`) inserts the CSV rows into
**empty** tables only, so it is safe to run repeatedly. On PostgreSQL it also moves the
`product_id` counter past the 1,500 loaded IDs, so new products get ID 1501 onward.

`scripts/ingestion/ingest_data.py` (psycopg2, PostgreSQL only) still works for the
original tables; `manage.py seed` replaces it for the ORM schema and works on both databases.

## 6. How the API Uses the Database

| Endpoint | Reads | Writes |
|---|---|---|
| `/ready` | connection, migration version, `materials` count | — |
| `/predict` | materials catalogue (once, at model load, for score scaling) | `prediction_history` |
| `/recommend` | `products` (by `product_id`), materials catalogue (once) | `recommendation_runs`, `recommendation_logs` |
| `/admin/stats` | row counts of every table | — |

- The catalogue is read from the `materials` table when the models load. If the table is
  empty, the API falls back to the CSV and logs a warning; `/ready` reports `materials: empty`.
- Sessions commit on success and roll back on any error (`Database.session()`).
- If saving history fails, the prediction is still returned, with a warning in the
  response and the full error in `logs/app.log`.
- On SQLite, foreign keys are switched on for every connection (SQLite ignores them by default).
- The database password is never logged; `/admin/stats` shows the URL with `***`.

## 7. Example Queries

```sql
-- Top recommendations ever made for product 1
SELECT r.created_at, l.material_rank, l.recommended_material_id, l.final_score
FROM recommendation_logs l JOIN recommendation_runs r USING (run_id)
WHERE l.product_id = 1 ORDER BY r.created_at DESC, l.material_rank;

-- How often each material is recommended at rank 1
SELECT recommended_material_id, COUNT(*) FROM recommendation_logs
WHERE material_rank = 1 GROUP BY recommended_material_id ORDER BY 2 DESC;

-- Share of predictions served from the cache
SELECT cached, COUNT(*) FROM prediction_history GROUP BY cached;
```
