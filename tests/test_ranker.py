"""
EcoPackAI - Material Ranking Tests
Module: Recommendation Engine

Checks the ranking logic on a small hand-made catalogue, so every
expected result can be verified by eye. Does not need the trained models.

Run with: pytest tests/test_ranker.py -v
"""

import copy
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from recommendation.ranker import (  # noqa: E402
    filter_candidates, load_config, prepare_materials, rank_all, rank_for_product,
    validate_config,
)

CONFIG = {
    "top_n": 3,
    "max_per_packaging_type": None,
    "default_mode": "balanced",
    "modes": {
        "balanced": {"co2": 0.30, "cost": 0.30, "suitability": 0.25, "sustainability": 0.15},
        "sustainability_first": {"co2": 0.45, "cost": 0.10, "suitability": 0.20, "sustainability": 0.25},
        "cost_first": {"co2": 0.15, "cost": 0.50, "suitability": 0.25, "sustainability": 0.10},
    },
    "category_suitability": {"Food": ["Food & Beverage"], "Electronics": ["Electronics", "Fragile Items"]},
    "constraints": {
        "min_recyclability_percent": 70,
        "max_cost_per_unit_usd": None,
        "min_load_handling_by_weight": [{"min_weight_kg": 5, "min_load_handling": 7}],
        "fragile_products": {"min_fragility_index": 4, "cushioning_tag": "Fragile Items",
                             "min_load_handling_otherwise": 7},
        "min_moisture_by_shipping": {"Sea": 6},
    },
    "suitability": {
        "base_weights": {"load_handling": 1.0, "moisture_resistance": 1.0, "thermal_resistance": 1.0},
        "fragility_load_boost": 1.0,
        "shipping_boosts": {"Sea": {"moisture_resistance": 1.0}},
    },
}

# id, packaging, tags, recyclability, compliance, load, moisture, thermal, cost, co2
ROWS = [
    ("M1", "Box", "Food & Beverage, E-commerce", 100, 90, 5, 4, 4, 5.0, 0.5),       # green, mid cost
    ("M2", "Wrap", "Food & Beverage", 75, 70, 8, 8, 7, 1.0, 1.5),                   # cheap, high CO2
    ("M3", "Box", "Food & Beverage", 60, 90, 9, 9, 9, 0.5, 0.2),                    # fails recyclability
    ("M4", "Filler", "Fragile Items, Cosmetics", 100, 80, 2, 2, 3, 2.0, 0.3),       # cushioning
    ("M5", "Crate", "Electronics", 90, 95, 8, 8, 7, 12.0, 1.5),                     # strong
    ("M6", "Wrap", "Low-Value Goods, Secondary Protection for Non-Fragile Items", 80, 70, 3, 8, 7, 1.0, 1.5),
    ("M7", "Box", "Food & Beverage", 95, 88, 5, 4, 4, 5.2, 0.5),                    # near-copy of M1
]


def make_materials():
    df = pd.DataFrame(ROWS, columns=[
        "material_id", "packaging_type", "suitable_product_categories",
        "recyclability_percent", "supplier_sustainability_compliance_percent",
        "load_handling_score", "moisture_resistance_score", "thermal_resistance_score",
        "predicted_cost_usd", "predicted_co2_per_kg",
    ])
    df["material_type"] = df["packaging_type"]
    return prepare_materials(df)


def make_product(**overrides):
    product = {"product_id": 1, "product_name": "Test", "category": "Food",
               "product_weight_kg": 0.5, "fragility_index": 2, "shipping_type": "Road"}
    product.update(overrides)
    return pd.Series(product)


@pytest.fixture
def materials():
    return make_materials()


def ids(frame):
    return list(frame["material_id"])


# ---- Business constraints ----

def test_low_recyclability_is_excluded(materials):
    assert "M3" not in ids(filter_candidates(make_product(), materials, CONFIG))


def test_category_must_match(materials):
    candidates = ids(filter_candidates(make_product(category="Food"), materials, CONFIG))
    assert set(candidates) == {"M1", "M2", "M7"}


def test_unknown_category_gets_no_candidates(materials):
    assert filter_candidates(make_product(category="Toys"), materials, CONFIG).empty


def test_non_fragile_text_does_not_count_as_fragile(materials):
    # M6 is weak and says "Non-Fragile Items": it must not pass as cushioning
    config = copy.deepcopy(CONFIG)
    config["category_suitability"]["Electronics"].append("Low-Value Goods")
    product = make_product(category="Electronics", fragility_index=5)
    assert "M6" not in ids(filter_candidates(product, materials, config))


def test_fragile_product_needs_cushioning_or_strength(materials):
    product = make_product(category="Electronics", fragility_index=5)
    assert set(ids(filter_candidates(product, materials, CONFIG))) == {"M4", "M5"}


def test_heavy_product_needs_load_handling(materials):
    product = make_product(product_weight_kg=8)
    assert ids(filter_candidates(product, materials, CONFIG)) == ["M2"]


def test_sea_shipping_needs_moisture_resistance(materials):
    product = make_product(shipping_type="Sea")
    assert ids(filter_candidates(product, materials, CONFIG)) == ["M2"]


def test_cost_ceiling_is_enforced(materials):
    config = copy.deepcopy(CONFIG)
    config["constraints"]["max_cost_per_unit_usd"] = 2.0
    assert ids(filter_candidates(make_product(), materials, config)) == ["M2"]


def test_no_valid_material_is_flagged(materials):
    product = make_product(shipping_type="Sea", product_weight_kg=8, fragility_index=5,
                           category="Electronics")
    config = copy.deepcopy(CONFIG)
    config["constraints"]["min_moisture_by_shipping"]["Sea"] = 10
    result = rank_for_product(product, materials, config, "balanced", 3)
    assert len(result) == 1
    assert result.iloc[0]["status"] == "no_valid_material"
    assert result.iloc[0]["n_candidates"] == 0


# ---- Ranking behaviour ----

def test_ranks_are_ordered_by_score(materials):
    result = rank_for_product(make_product(), materials, CONFIG, "balanced", 3)
    assert list(result["rank"]) == list(range(1, len(result) + 1))
    assert result["final_score"].is_monotonic_decreasing


def test_modes_change_the_winner(materials):
    product = make_product()
    green = rank_for_product(product, materials, CONFIG, "sustainability_first", 1)
    cheap = rank_for_product(product, materials, CONFIG, "cost_first", 1)
    assert green.iloc[0]["material_id"] == "M1"   # lowest CO2, best recyclability
    assert cheap.iloc[0]["material_id"] == "M2"   # lowest cost


def test_ranking_is_deterministic(materials):
    products = pd.DataFrame([make_product(product_id=i) for i in range(3)])
    first = rank_all(products, materials, CONFIG, modes=["balanced", "cost_first"])
    second = rank_all(products, materials, CONFIG, modes=["balanced", "cost_first"])
    pd.testing.assert_frame_equal(first, second)


def test_top_n_limits_results(materials):
    product = make_product(category="Electronics")
    assert len(rank_for_product(product, materials, CONFIG, "balanced", 1)) == 1


def test_packaging_type_cap_adds_variety(materials):
    product = make_product(fragility_index=1)
    without_cap = rank_for_product(product, materials, CONFIG, "sustainability_first", 2)
    assert list(without_cap["packaging_type"]) == ["Box", "Box"]

    config = copy.deepcopy(CONFIG)
    config["max_per_packaging_type"] = 1
    with_cap = rank_for_product(product, materials, config, "sustainability_first", 2)
    assert list(with_cap["packaging_type"]) == ["Box", "Wrap"]


# ---- Configuration ----

def test_weights_must_sum_to_one():
    config = copy.deepcopy(CONFIG)
    config["modes"]["balanced"]["co2"] = 0.9
    with pytest.raises(ValueError, match="sum to"):
        validate_config(config)


def test_unknown_mode_is_rejected(materials):
    with pytest.raises(ValueError, match="Unknown mode"):
        rank_all(pd.DataFrame([make_product()]), materials, CONFIG, modes=["fastest"])


def test_project_config_file_is_valid():
    config = load_config(Path(__file__).resolve().parents[1] / "config" / "ranking_weights.yaml")
    assert set(config["modes"]) == {"balanced", "sustainability_first", "cost_first"}
