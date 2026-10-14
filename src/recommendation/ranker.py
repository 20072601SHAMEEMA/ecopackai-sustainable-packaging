"""
EcoPackAI - Material Ranking Logic
Module: Recommendation Engine

Ranks packaging materials for each product using predicted cost
(Random Forest), predicted CO2 (XGBoost), product-specific suitability
and sustainability indicators. Weights, thresholds and file paths come
from config/ranking_weights.yaml, so they can change without code edits.

Usage (from the project root):
    python src/recommendation/ranker.py
    python src/recommendation/ranker.py --modes balanced --top-n 3
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # make src/ importable
from inference.predictor import MaterialPredictor  # noqa: E402

DEFAULT_CONFIG = Path("config/ranking_weights.yaml")
CRITERIA = ["co2", "cost", "suitability", "sustainability"]
SCORE_COLUMNS = {
    "load_handling": "load_handling_score",
    "moisture_resistance": "moisture_resistance_score",
    "thermal_resistance": "thermal_resistance_score",
}

OUTPUT_COLUMNS = [
    "mode", "product_id", "product_name", "category", "product_weight_kg",
    "fragility_index", "shipping_type", "rank", "material_id", "material_type",
    "packaging_type", "final_score", "predicted_cost_usd", "predicted_co2_per_kg",
    "recyclability_percent", "supplier_sustainability_compliance_percent",
    "load_handling_score", "moisture_resistance_score", "thermal_resistance_score",
    "score_co2", "score_cost", "score_suitability", "score_sustainability",
    "n_candidates", "status",
]


def load_config(path=DEFAULT_CONFIG) -> dict:
    """Read the YAML config and check that it is usable."""
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    validate_config(config)
    return config


def validate_config(config: dict) -> None:
    """Fail early with a clear message if weights or modes are wrong."""
    for mode, weights in config["modes"].items():
        missing = set(CRITERIA) - set(weights)
        if missing:
            raise ValueError(f"Mode '{mode}' is missing weights for: {sorted(missing)}")
        total = sum(weights[c] for c in CRITERIA)
        if not np.isclose(total, 1.0):
            raise ValueError(f"Weights for mode '{mode}' sum to {total:.3f}, expected 1.0")
        if any(weights[c] < 0 for c in CRITERIA):
            raise ValueError(f"Mode '{mode}' has a negative weight")
    if config["default_mode"] not in config["modes"]:
        raise ValueError(f"default_mode '{config['default_mode']}' is not a defined mode")


def add_predictions(materials: pd.DataFrame, predictor: MaterialPredictor) -> pd.DataFrame:
    """Predict cost and CO2 for every material through the packaged predictor."""
    predictions = predictor.predict(materials)
    out = materials.copy()
    out["predicted_cost_usd"] = predictions["predicted_cost_usd"]
    out["predicted_co2_per_kg"] = predictions["predicted_co2_per_kg"]
    return out


def _min_max(values: pd.Series, higher_is_better: bool) -> pd.Series:
    """Scale to 0-1 across the whole catalogue, where 1 is always best."""
    low, high = values.min(), values.max()
    if high == low:
        return pd.Series(1.0, index=values.index)
    scaled = (values - low) / (high - low)
    return scaled if higher_is_better else 1 - scaled


def prepare_materials(materials: pd.DataFrame) -> pd.DataFrame:
    """Add the product-independent criterion scores and parsed category tags.

    Expects predicted_cost_usd and predicted_co2_per_kg (see add_predictions).
    Normalising over the full catalogue keeps scores comparable between products.
    """
    out = materials.copy()
    out["tags"] = out["suitable_product_categories"].apply(
        lambda text: frozenset(t.strip().lower() for t in text.split(","))
    )
    out["score_co2"] = _min_max(out["predicted_co2_per_kg"], higher_is_better=False)
    out["score_cost"] = _min_max(out["predicted_cost_usd"], higher_is_better=False)
    out["score_sustainability"] = (
        _min_max(out["recyclability_percent"], higher_is_better=True)
        + _min_max(out["supplier_sustainability_compliance_percent"], higher_is_better=True)
    ) / 2
    return out


def filter_candidates(product: pd.Series, materials: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Keep only materials that pass every hard constraint for this product."""
    rules = config["constraints"]
    allowed = {t.lower() for t in config["category_suitability"].get(product["category"], [])}

    mask = materials["tags"].apply(lambda tags: bool(tags & allowed))
    mask &= materials["recyclability_percent"] >= rules["min_recyclability_percent"]

    if rules.get("max_cost_per_unit_usd") is not None:
        mask &= materials["predicted_cost_usd"] <= rules["max_cost_per_unit_usd"]

    min_load = 0
    for band in sorted(rules["min_load_handling_by_weight"], key=lambda b: b["min_weight_kg"]):
        if product["product_weight_kg"] >= band["min_weight_kg"]:
            min_load = band["min_load_handling"]
    mask &= materials["load_handling_score"] >= min_load

    fragile = rules["fragile_products"]
    if product["fragility_index"] >= fragile["min_fragility_index"]:
        cushioning = materials["tags"].apply(lambda tags: fragile["cushioning_tag"].lower() in tags)
        strong = materials["load_handling_score"] >= fragile["min_load_handling_otherwise"]
        mask &= cushioning | strong

    min_moisture = rules["min_moisture_by_shipping"].get(product["shipping_type"], 0)
    mask &= materials["moisture_resistance_score"] >= min_moisture

    return materials[mask]


def suitability_scores(product: pd.Series, candidates: pd.DataFrame, config: dict) -> pd.Series:
    """Weighted average of load/moisture/thermal scores (1-10), tuned to the product."""
    settings = config["suitability"]
    weights = dict(settings["base_weights"])
    weights["load_handling"] += settings["fragility_load_boost"] * (product["fragility_index"] - 1) / 4
    for prop, boost in settings["shipping_boosts"].get(product["shipping_type"], {}).items():
        weights[prop] += boost

    total = sum(weights.values())
    weighted = sum(w * candidates[SCORE_COLUMNS[prop]] / 10 for prop, w in weights.items())
    return weighted / total


def rank_for_product(product: pd.Series, materials: pd.DataFrame, config: dict,
                     mode: str, top_n: int) -> pd.DataFrame:
    """Return the top-N materials for one product (or one flagged row if none qualify)."""
    product_info = {
        "mode": mode,
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "category": product["category"],
        "product_weight_kg": product["product_weight_kg"],
        "fragility_index": product["fragility_index"],
        "shipping_type": product["shipping_type"],
    }

    candidates = filter_candidates(product, materials, config).copy()
    if candidates.empty:
        return pd.DataFrame([{**product_info, "n_candidates": 0, "status": "no_valid_material"}],
                            columns=OUTPUT_COLUMNS).astype({"n_candidates": int})

    weights = config["modes"][mode]
    candidates["score_suitability"] = suitability_scores(product, candidates, config)
    candidates["final_score"] = 100 * sum(weights[c] * candidates[f"score_{c}"] for c in CRITERIA)

    # Sort by score; ties broken by material_id so results are always identical
    ordered = candidates.sort_values(["final_score", "material_id"], ascending=[False, True],
                                     kind="mergesort")
    top = _select_top(ordered, top_n, config.get("max_per_packaging_type"))
    top = top.assign(**product_info, rank=range(1, len(top) + 1),
                     n_candidates=len(candidates), status="ok")
    return top[OUTPUT_COLUMNS]


def _select_top(ordered: pd.DataFrame, top_n: int, max_per_type) -> pd.DataFrame:
    """Take the best top_n rows, allowing at most max_per_type per packaging type.

    If the cap leaves fewer than top_n rows (few packaging types qualify), the
    remaining places are filled with the next best materials regardless of type.
    """
    if not max_per_type:
        return ordered.head(top_n)
    within_cap = ordered.groupby("packaging_type").cumcount() < max_per_type
    top = ordered[within_cap].head(top_n)
    if len(top) < top_n:
        filler = ordered.drop(top.index).head(top_n - len(top))
        top = pd.concat([top, filler])
    return top.sort_values(["final_score", "material_id"], ascending=[False, True], kind="mergesort")


def rank_all(products: pd.DataFrame, materials: pd.DataFrame, config: dict,
             modes=None, top_n=None) -> pd.DataFrame:
    """Rank materials for every product in every requested mode."""
    modes = modes or [config["default_mode"]]
    top_n = top_n or config["top_n"]
    for mode in modes:
        if mode not in config["modes"]:
            raise ValueError(f"Unknown mode '{mode}'. Available: {list(config['modes'])}")

    records = [
        record
        for mode in modes
        for _, product in products.iterrows()
        for record in rank_for_product(product, materials, config, mode, top_n).to_dict("records")
    ]
    rankings = pd.DataFrame(records, columns=OUTPUT_COLUMNS)
    return rankings.astype({"rank": "Int64", "n_candidates": int})


def main():
    parser = argparse.ArgumentParser(description="Rank packaging materials for each product.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to ranking_weights.yaml")
    parser.add_argument("--modes", nargs="+", help="ranking modes (default: all modes in the config)")
    parser.add_argument("--top-n", type=int, help="materials per product (default: from config)")
    parser.add_argument("--output", help="output CSV path (default: from config)")
    args = parser.parse_args()

    config = load_config(args.config)
    paths = config["paths"]
    modes = args.modes or list(config["modes"])

    materials = pd.read_csv(paths["materials"])
    products = pd.read_csv(paths["products"])

    materials = prepare_materials(add_predictions(materials, MaterialPredictor()))
    rankings = rank_all(products, materials, config, modes=modes, top_n=args.top_n)

    output = Path(args.output or paths["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    rankings.round(4).to_csv(output, index=False)

    flagged = rankings.loc[rankings["status"] == "no_valid_material", "product_id"].nunique()
    print(f"Ranked {products.shape[0]} products x {len(modes)} modes -> {len(rankings)} rows")
    print(f"Products with no valid material: {flagged}")
    print(f"Saved to {output}")


if __name__ == "__main__":
    main()
