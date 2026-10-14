"""
EcoPackAI - Cache Performance Benchmark
Module: Flask Backend - Performance

Measures API latency for the same requests with the response cache OFF and
ON (warm), through Flask's test client. By default it uses a temporary SQLite
database (migrated and seeded on the fly), so benchmark traffic never lands in
your real prediction_history. Writes outputs/benchmarks/cache_benchmark.csv.

Usage (from the project root):
    python scripts/benchmark_cache.py                       # 30 timed requests per scenario
    python scripts/benchmark_cache.py --repeats 100
    python scripts/benchmark_cache.py --database-url postgresql://user:pass@host/benchdb
"""

import argparse
import json
import logging
import statistics
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from db import Database  # noqa: E402
from db.seed import seed  # noqa: E402
from manage import migrate  # noqa: E402

KEY = "benchmark-key"


def scenarios():
    materials = json.loads(pd.read_csv(ROOT / "data" / "processed" / "materials.csv").to_json(orient="records"))
    product = {"category": "Food", "product_weight_kg": 0.5, "fragility_index": 2, "shipping_type": "Road"}
    return [
        ("/predict - 1 material", "/predict", {"material": materials[0]}),
        ("/predict - 20 materials + product", "/predict", {"materials": materials[:20], "product": product}),
        ("/predict - 100 materials + product", "/predict", {"materials": materials[:100], "product": product}),
        ("/recommend - product_id (database lookup)", "/recommend", {"product_id": 1}),
        ("/recommend - inline product", "/recommend", {"product": product}),
    ]


def measure(client, path, body, repeats):
    times = []
    for _ in range(repeats):
        started = time.perf_counter()
        response = client.post(path, json=body, headers={"X-API-Key": KEY})
        times.append((time.perf_counter() - started) * 1000)
        assert response.status_code == 200, response.get_json()
    return times, response.headers.get("X-Cache")


def main():
    parser = argparse.ArgumentParser(description="EcoPackAI cache performance benchmark")
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--database-url", help="database to use (default: a temporary SQLite file)")
    args = parser.parse_args()

    workdir = tempfile.TemporaryDirectory()
    url = args.database_url or f"sqlite:///{Path(workdir.name, 'benchmark.db').as_posix()}"
    migrate(url)
    seed(Database(url))

    rows = []
    for cache_on in (False, True):
        app = create_app({"API_KEYS": (KEY,), "ADMIN_API_KEYS": (), "CACHE_ENABLED": cache_on,
                          "DATABASE_URL": url, "LOG_DIR": str(Path(workdir.name, "logs"))})
        logging.getLogger("ecopackai").setLevel(logging.WARNING)      # keep the console readable
        client = app.test_client()
        app.extensions["ecopackai"].service.load()                    # exclude one-off model loading
        for name, path, body in scenarios():
            client.post(path, json=body, headers={"X-API-Key": KEY})  # warm-up (fills the cache when ON)
            times, cache_header = measure(client, path, body, args.repeats)
            rows.append({"scenario": name, "cache": "on" if cache_on else "off", "x_cache": cache_header,
                         "median_ms": round(statistics.median(times), 2),
                         "p95_ms": round(sorted(times)[int(0.95 * (len(times) - 1))], 2),
                         "repeats": args.repeats})
        app.extensions["ecopackai"].db.engine.dispose()

    results = pd.DataFrame(rows)
    table = results.pivot(index="scenario", columns="cache", values="median_ms")[["off", "on"]]
    table["speed-up"] = (table["off"] / table["on"]).round(1).astype(str) + "x"
    table = table.loc[[name for name, _, _ in scenarios()]]
    out = ROOT / "outputs" / "benchmarks"
    out.mkdir(parents=True, exist_ok=True)
    results.to_csv(out / "cache_benchmark.csv", index=False)

    backend = url.split(":", 1)[0]
    print(f"\nMedian latency in ms ({args.repeats} requests each, database: {backend})\n")
    print(table.rename(columns={"off": "cache off", "on": "cache on (warm)"}).to_string())
    print(f"\nSaved {(out / 'cache_benchmark.csv').relative_to(ROOT)}")

    logging.shutdown()                       # release the log files before the temp folder is removed
    workdir.cleanup()


if __name__ == "__main__":
    main()
