# Frontend ↔ Backend Integration — Recommendations

| Part | Location |
|---|---|
| API integration logic (request, loading, errors, inline results) | `frontend/static/js/predict.js` |
| Table rendering, sorting, response check | `frontend/static/js/recommendation_table.js` (shared by both pages) |
| Full analysis page (charts, mode switch, exports) | `frontend/static/js/results.js`, `charts.js` |
| Backend endpoint | `POST /recommend` — `backend/routes/recommend.py` (`docs/api.md`) |
| Tests | `tests/frontend/recommendation_table.test.js` (Node), `tests/test_frontend.py`, `tests/e2e/test_ui_flows.py` |

## 1. Which Endpoint: `/recommend` (not `/predict`)

The brief names `/predict`. In this API the two prediction endpoints do different jobs:

| Endpoint | Input | Output |
|---|---|---|
| `POST /predict` | Up to 100 **materials**, each with 18 attributes (recyclability, CO₂ footprint, …) | Cost and CO₂ prediction per given material |
| `POST /recommend` | One **product** (category, weight, fragility, shipping) | The whole catalogue filtered, predicted (same models) and **ranked** for that product |

A user filling in the product form knows the product, not 18 attributes of every
material, and the brief's goal is "receive ranked sustainable packaging recommendations".
So the form calls `/recommend`, which runs the same packaged prediction models
(`src/inference/predictor.py`) as `/predict` and adds the ranking. `/predict` stays
available for systems that want predictions for their own materials.

## 2. Request Flow

```
User fills form ──► predict.js validates every field (docs/frontend_validation.md)
                     │ invalid → errors under the fields + summary; NO request is sent
                     ▼ valid
                    POST /recommend  (JSON, X-API-Key, 15 s timeout)
                     │ button disabled + spinner + "Ranking materials for your product..."
                     ▼
                    response ──► 200 + status "success"
                     │             ├─ validateRecommendResponse() fails → "response was incomplete" message
                     │             └─ valid → table rendered UNDER THE FORM (no page reload),
                     │                        stored in sessionStorage for results.html
                     ├─ 400 → server messages shown on the matching fields
                     ├─ 401 / 403 → "needs a valid client key", API settings opened
                     ├─ other HTTP error → server message + request ID
                     └─ no answer / network error → "Cannot reach the API ..." / "did not answer within 15 s"
```

Submitting again (e.g. another ranking mode) replaces the table in place. "View charts &
export" opens `results.html`, which reads the stored response: charts, mode switch, CSV/PDF.

## 3. Data Mapping (Form → JSON → Backend)

| Form field | JSON field | Type sent | Backend rule (`/recommend`) |
|---|---|---|---|
| Product name | `product.product_name` | string (trimmed) | optional; stored with the run, used in export file names |
| Product category | `product.category` | string | one of the 6 categories in `config/ranking_weights.yaml` |
| Weight (kg) | `product.product_weight_kg` | number | > 0 |
| Fragility index | `product.fragility_index` | integer | 1–5 |
| Shipping type | `product.shipping_type` | string | Air, Road, Sea |
| Ranking mode | `options.mode` | string | balanced (default), sustainability_first, cost_first |
| Number of recommendations | `options.top_n` | integer | 1–20 (default 5) |
| API settings → client key | header `X-API-Key` | — | required when the server has API keys |

```json
{"product": {"product_name": "Chocolate Box", "category": "Food", "product_weight_kg": 0.5,
             "fragility_index": 2, "shipping_type": "Air"},
 "options": {"mode": "balanced", "top_n": 5}}
```

Numbers are converted from the text inputs to JSON numbers by `buildPayload()`; the
frontend rules equal the backend rules (checked by `tests/test_frontend.py`).

## 4. Response Schema Reference (fields the UI uses)

| Field | Type / rule checked by `validateRecommendResponse()` | Used for |
|---|---|---|
| `status` | must be `"success"` | — |
| `result` | `"ok"` or `"no_valid_material"`; must agree with the list (ok ⇒ not empty, no_valid ⇒ empty) | table vs. "No suitable material" message |
| `product` | object | summary line, results page, exports |
| `mode` | string | summary line, mode buttons |
| `n_candidates` | integer | "N materials passed the constraints" |
| `recommendations[]` | list; ranks must run 1, 2, 3, … | table rows, charts |
| `.rank` | integer ≥ 1 | Rank column, top-pick highlight |
| `.material_id`, `.material_type`, `.packaging_type` | non-empty strings | Material and Packaging columns |
| `.final_score` | number 0–100 | Sustainability score column (bar + value) |
| `.predicted_cost_usd` | number ≥ 0 | Cost / unit column |
| `.predicted_co2_per_kg` | number ≥ 0 | CO₂ column |
| `.recyclability_percent` | number 0–100 | Recyclable column |
| `.scores` | object (not required) | chart tooltips |
| `run_id`, `request_id` | — (optional) | export buttons, error references |

Every problem is reported by name (e.g. "recommendation 1: predicted_cost_usd is missing
or invalid"). A response that fails the check is **never shown or stored**: the user sees
"The API answered, but the response was incomplete …" with the request ID. On
`results.html`, a damaged stored result falls back to the labelled sample; a damaged
mode-switch response keeps the previous results on screen.

**Empty and fallback responses**

| Situation | What the user sees |
|---|---|
| `result: "no_valid_material"` (e.g. fragile drinkware by sea) | "No suitable material found" with advice, under the form and on the results page; table hidden |
| `results.html` opened with no result in this tab | Labelled sample result (real API output for a chocolate box); exports disabled |

## 5. Data-Binding Plan

| Response data | Form page (`predict.html`) | Results page (`results.html`) |
|---|---|---|
| `product`, `mode`, `n_candidates` | `#inline-summary` line | `#product-summary` list |
| `recommendations[]` | `#inline-table` (sortable) | `#results-table` (sortable), best-choice card |
| `recommendations[]` values | — | 3 charts (`charts.js`), same values, no rounding |
| `result = no_valid_material` | `#inline-no-result` | `#no-result` |
| `run_id` | — | CSV / PDF export buttons |
| `warnings[]` | — | yellow notices above the table |
| whole response | stored in `sessionStorage` (`ecopackai:lastResult`, this tab only) | read on page load; replaced by the mode switch |

## 6. Table Layout

Both pages use the same table (`recommendation_table.js`):

| Column | Shows | Format | Sort (first click) |
|---|---|---|---|
| Rank | `rank` | `#1` | ascending (default order) |
| Material | `material_id`, `material_type` below; "Top pick" badge on rank 1 | text | A → Z |
| Packaging type | `packaging_type` | text | A → Z |
| Sustainability score / Final score | `final_score` | bar + 1 decimal | highest first |
| Cost / unit | `predicted_cost_usd` | `$` + 2 decimals | cheapest first |
| CO₂ | `predicted_co2_per_kg` | 3 decimals (kg CO₂ per kg) | lowest first |
| Recyclable | `recyclability_percent` | 0 decimals + `%` | highest first |

- **Sorting:** every heading is a button; clicking again reverses the order. The active
  column shows ▲/▼ and has `aria-sort` for screen readers. Equal values keep rank order.
  Sorting only reorders rows; values are never changed.
- **Highlighting:** the rank-1 row has a green background and a "Top pick" badge in any
  sort order; the results page also has a "Best choice" card.
- **Responsive:** the table sits in a Bootstrap `.table-responsive` card, so on narrow
  screens it scrolls inside the card instead of widening the page; tested at 768 px.

## 7. Verification

| Brief checklist item | Evidence |
|---|---|
| Frontend sends product input to the API | E2E: one `POST /recommend` with status 200 per submit; no request for invalid input |
| Backend returns ranked recommendation data | E2E: response has ranks 1…N; `/recommend` results equal `outputs/material_rankings.csv` (API tests) |
| Table updates dynamically without page reload | E2E `test_results_appear_under_the_form_without_a_page_reload`: a marker set before submitting survives, no navigation happens, and a second submit updates the same table. With a reload planted back in, this test fails |
| API failures handled with clear feedback | E2E: connection refused, HTTP 500 with request ID, missing key (401), incomplete response |
| Data displayed matches backend predictions | E2E: every table cell equals the API response on both pages, in Chromium and Firefox |
| Sorting / highlighting | E2E: cost and CO₂ columns sort both ways with `aria-sort`; top pick highlighted; results-page table sortable |
| Response schema consistency | 13 Node unit tests + E2E rejection of an incomplete response |
