# Material Ranking Logic — EcoPackAI Recommendation Engine

**Module:** `src/recommendation/ranker.py` · **Config:** `config/ranking_weights.yaml`
**Output:** `outputs/material_rankings.csv` · **Tests:** `tests/test_ranker.py`

## 1. Purpose

Turns the two trained models (`rf_cost.joblib`, `xgb_co2.joblib`) into recommendations:
for every product, rank the packaging materials that are allowed for it and return the
top N, in three ranking modes.

## 2. Inputs

| Input | Source |
|---|---|
| Materials (403) | `data/processed/materials.csv` |
| Products (1,500) | `data/processed/products.csv` |
| Predicted cost per unit (USD) | Random Forest pipeline, `ml/models/rf_cost.joblib` |
| Predicted CO2 per kg | XGBoost pipeline, `ml/models/xgb_co2.joblib` |
| Weights, thresholds, paths | `config/ranking_weights.yaml` |

Predictions are used rather than the catalogue's own cost/CO2 values so the same logic
works for new materials whose cost and CO2 are unknown.

## 3. Linking Products to Materials

The datasets share no key. Each material lists the product groups it suits
(`suitable_product_categories`, e.g. "Fragile Items, Cosmetics, Pharmaceuticals").
`category_suitability` in the config maps each product category to the groups it may use:

| Product category | Allowed material groups |
|---|---|
| Food | Food & Beverage, Consumer Goods, Low-Value Goods |
| Drinkware | Food & Beverage, Fragile Items |
| Electronics | Electronics, Fragile Items, E-commerce |
| Cosmetics | Cosmetics, Consumer Goods |
| Pharmacy | Pharmaceuticals, E-commerce |
| Paper Product | E-commerce, Consumer Goods, Low-Value Goods |

Groups are matched as **exact list entries** (case-insensitive). Plain text search would
wrongly match "Fragile Items" inside "Secondary Protection for Non-Fragile Items".
Industrial materials (steel racks, plastic totes and pallets) match no consumer category.

## 4. Hard Constraints (filters)

A material failing any rule is never ranked for that product.

| Rule | Default | Rationale |
|---|---|---|
| Category match | see section 3 | Material must suit the product type |
| Minimum recyclability | 70% | Sustainability floor |
| Cost ceiling | none (optional) | Budget limit when set |
| Load handling by weight | ≥ 5 for products ≥ 2 kg; ≥ 7 for ≥ 5 kg | Heavy products need strong packaging |
| Fragile products (fragility ≥ 4) | cushioning material ("Fragile Items") **or** load handling ≥ 7 | Fragile goods need cushioning or a rigid container |
| Sea shipping | moisture resistance ≥ 6 | Humidity at sea |

If no material passes, the product gets one row with `status = no_valid_material`
instead of an unsafe recommendation.

## 5. Ranking Criteria and Normalisation

Every criterion is scaled to 0–1, where **1 is always best**. Cost, CO2 and
sustainability use min-max scaling over the **whole catalogue**, so scores are comparable
across products.

| Criterion | Formula | Direction |
|---|---|---|
| `score_co2` | 1 − minmax(predicted CO2 per kg) | lower CO2 is better |
| `score_cost` | 1 − minmax(predicted cost per unit) | lower cost is better |
| `score_sustainability` | mean of minmax(recyclability %) and minmax(supplier compliance %) | higher is better |
| `score_suitability` | weighted mean of load, moisture, thermal scores / 10 | higher is better |

**Suitability is product-specific.** Base weight 1 for each property, plus:
load handling + 1.0 × (fragility − 1) / 4 (double weight at fragility 5);
moisture + 1.0 for sea; thermal + 0.5 for air.

## 6. Composite Score and Modes

`final_score = 100 × Σ weight_c × score_c`, weights per mode (each mode sums to 1.0):

| Mode | CO2 | Cost | Suitability | Sustainability |
|---|---|---|---|---|
| balanced (default) | 0.30 | 0.30 | 0.25 | 0.15 |
| sustainability_first | 0.45 | 0.10 | 0.20 | 0.25 |
| cost_first | 0.15 | 0.50 | 0.25 | 0.10 |

The config is validated on load: weights must be non-negative and sum to 1.0.

## 7. Sorting, Top-N and Determinism

- Sorted by `final_score` (descending), ties broken by `material_id`, with a stable sort.
  Two full runs produce byte-identical output.
- `top_n = 5` per product and mode.
- `max_per_packaging_type = 2`: without it, near-identical materials of one type fill the
  whole list (e.g. five cardboard boxes). If fewer than 5 fit under the cap, the remaining
  places go to the next best materials regardless of type. Set to `null` for pure score order.

## 8. Output — `outputs/material_rankings.csv`

One row per (mode, product, rank): product details, `rank`, material ID/type/packaging,
`final_score`, predicted cost and CO2, recyclability, compliance, load/moisture/thermal
scores, the four criterion scores, `n_candidates` (materials that passed the filters)
and `status` (`ok` / `no_valid_material`).

1,500 products × 3 modes → 21,984 rows (43 products × 3 modes are flagged rows).

## 9. Results

| Check | Result |
|---|---|
| Products ranked | 1,457 of 1,500 (top 5 in each mode) |
| No valid material | 43 Drinkware products shipped by Sea (41 with fragility 4, 2 with fragility 3) |
| Packaging types in a balanced top 5 | 2 types: 1,214 products; 3 types: 83; 1 type: 160 |
| Balanced #1 picks vs catalogue | CO2 0.54 vs 1.15 kg/kg (−53%); recyclability 99.5% vs 91.6% |

**Examples (balanced mode):**
- *Chocolate Box* (Food, 0.5 kg, fragility 2, Air): cardboard boxes (score 81.6) lead.
  In cost_first mode bubble wrap moves to #1 ($1.24 vs $2.79) despite ~3× the CO2.
- *Smartphone* (Electronics, fragility 5, Air): only cushioning fillers or strong
  containers qualify; paper fillers rank 1–3 ($1.9, 0.31 kg CO2/kg), foldable plastic
  containers 4–5 ($12, 1.48 kg CO2/kg).
- *Wine Bottle* (Drinkware, fragility 4, Sea): `no_valid_material`.

**Catalogue gap:** fragile drinkware shipped by sea has no valid single material.
Cushioning fillers fail the moisture rule (moisture 1–3) and cardboard boxes fail the
fragility rule (load 4–6). The catalogue needs a moisture-resistant cushioning material,
or the business must accept a relaxed rule in the config.

## 10. Validation

`tests/test_ranker.py` (17 tests, synthetic 7-material catalogue, no models needed):

| Checklist item | Tests |
|---|---|
| Deterministic results | `test_ranking_is_deterministic`, plus two identical full runs |
| Correct ranking for multiple products | `test_ranks_are_ordered_by_score`, `test_modes_change_the_winner`, `test_top_n_limits_results`, `test_packaging_type_cap_adds_variety` |
| Configurable without code changes | all settings in YAML; `test_project_config_file_is_valid`, `test_weights_must_sum_to_one`, `test_unknown_mode_is_rejected` |
| Business constraints enforced | recyclability, category, non-fragile text, fragility, weight, sea moisture, cost ceiling, no-valid-material tests |
| Aligned with sustainability goals | section 9: top picks have 53% lower CO2 and higher recyclability than the catalogue average |

## 11. Limitations

- Cost and CO2 predictions are per material, not per product; product attributes affect
  the ranking through filters and suitability only.
- Thresholds are reasoned business defaults, not values learned from data; they live in
  the config so the business can tune them.
- One material per product: real shipments often combine materials (box + filler).

## 12. Usage

```bash
python src/recommendation/ranker.py                          # all modes, top 5
python src/recommendation/ranker.py --modes cost_first --top-n 3
pytest tests/test_ranker.py -v
```

From Python (e.g. the Flask API):

```python
from recommendation.ranker import load_config, add_predictions, prepare_materials, rank_for_product
```
