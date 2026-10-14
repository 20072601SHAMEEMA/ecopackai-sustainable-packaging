# Analytics Charts & Report Export

| Part | Location |
|---|---|
| Chart logic | `frontend/static/js/charts.js` (Chart.js 4.4.4) |
| Results page logic | `frontend/static/js/results.js` (rendering, mode switch, export buttons) |
| Shared sortable table + response check | `frontend/static/js/recommendation_table.js` (`docs/ui_integration.md`) |
| Export endpoints | `backend/routes/reports.py` (`GET /reports/<run_id>.csv`, `.pdf`) |
| Libraries (shipped with the project) | `frontend/static/vendor/` (Bootstrap 5.3.3, Chart.js 4.4.4, licences) |
| Tests | `tests/frontend/charts.test.js`, `tests/test_reports.py`, `tests/e2e/test_ui_flows.py` |
| Screenshots | `docs/screenshots/results-desktop.png`, `results-tablet.png`, `results-charts-tooltip.png` |

## 1. Charts on the Results Page

Below the results table, "Compare the recommended materials" shows three charts:

| Chart | Type | Shows | Tooltip |
|---|---|---|---|
| Predicted CO₂ footprint | Bar | `predicted_co2_per_kg` of each recommended material | "Bubble Wrap (Minimal Use): 1.476 kg CO₂ per kg" |
| Predicted cost per unit | Bar | `predicted_cost_usd` of each material | "Cardboard Boxes: $2.79 per unit" |
| Sustainability score ranking | Horizontal bar, 0–100 | `final_score` in rank order | Final score plus the 4 criterion scores: "CO₂ score 93%, Cost score 91%, Suitability 53%, Sustainability 86%" |

- Bars are labelled `#rank material_id`, in the same order as the table.
- **Colour = packaging type**, identical in all three charts; the legend lists the types and
  clicking one hides or shows its bars.
- Axes are titled with units; the score axis is fixed to 0–100 so modes can be compared.
- Charts resize with the window (fixed height, responsive width); on tablets the two bar
  charts stack. Each canvas has an `aria-label`; exact values are in the table.

**Data binding.** `charts.js` builds the charts only from the `/recommend` response
(`chartData()`), with no rounding: chart values are the API values. The table, best-choice
card, charts and exports all come from the same response.

**Automatic updates.** The ranking-mode buttons (Balanced / Sustainability first / Cost
first) call `/recommend` again for the same product. The new response replaces the stored
one, and the table, product summary, charts (updated in place) and export buttons all
re-render. A spinner shows while waiting, and failures appear as a message without losing
the current results.

## 2. Export

| Button | Request | File |
|---|---|---|
| Results (CSV) | `GET /reports/<run_id>.csv` | `ecopackai_recommendations_<product>_<YYYYMMDD-HHMMSS>_run<id>.csv` |
| Summary (PDF) | `GET /reports/<run_id>.pdf` | `ecopackai_sustainability_summary_<product>_<YYYYMMDD-HHMMSS>_run<id>.pdf` |

**Naming convention.** `<product>` is the product name in lowercase ASCII with dashes
("Crème Brûlée Jar" → `creme-brulee-jar`, max 40 characters, `product` if unnamed);
the timestamp is when the recommendation was made (UTC); `run<id>` is the saved run.
Files of different recommendations never overwrite each other, and the name tells you
which run a file came from.

**Why exports match the screen.** Every `/recommend` call is saved as a run
(`recommendation_runs` + `recommendation_logs`). The export endpoints rebuild the files
from that saved run, joined with the material catalogue for type, packaging and
recyclability, so they contain exactly the values the API returned and the page displays.
The tests check this value by value.

### CSV format

UTF-8 with BOM (so Excel shows accents correctly), comma-separated, header row, one row
per recommended material:

| Column | Example |
|---|---|
| `run_id`, `recommended_at_utc` | `12`, `2026-10-06T04:04:12Z` |
| `product_name`, `category`, `product_weight_kg`, `fragility_index`, `shipping_type`, `mode` | `Chocolate Box`, `Food`, `0.5`, `2`, `Air`, `balanced` |
| `rank`, `material_id`, `material_type`, `packaging_type` | `1`, `MAT_0154`, `Cardboard`, `Cardboard Boxes` |
| `final_score`, `predicted_cost_usd`, `predicted_co2_per_kg`, `recyclability_percent` | `81.5715`, `2.7885`, `0.5102`, `100.0` |

Numbers keep the API's 4-decimal precision; the page shows them rounded (score 1, cost 2,
CO₂ 3 decimals). A run with no valid material produces the header row only.

### PDF format (A4, one page for 5 materials)

1. Title, run number, time (UTC) and request ID
2. Product details, ranking mode, number of materials that passed the constraints
3. Best choice: material, packaging, score, cost, CO₂, recyclability
4. Sustainability summary: average predicted CO₂ of the recommended materials versus the
   catalogue average, cost range, recyclability range
5. Table of all recommended materials (long packaging names shrink to fit their column)
6. Bar chart of final scores
7. Footnote: models used and how the score is computed

A run with no valid material produces a PDF explaining why. The built-in PDF fonts cover
Latin-1, so accented names print correctly; other characters are replaced with "?".

### Rules

- Exports need the client API key (same as `/recommend`); without it: 401.
- Unknown run: 404. Only `.csv` and `.pdf` exist.
- On the sample results page (no run of your own yet) the buttons are disabled with an
  explanation, because there is no saved run to export.

## 3. Libraries Shipped With the Project

Bootstrap and Chart.js were first loaded from a CDN. End-to-end testing on a slow network
showed the weakness: downloads failed or arrived incomplete, and the browser (correctly)
refused them, leaving pages without styles, charts or working buttons. Both libraries are
now in `frontend/static/vendor/`, so the app works fully offline and loads the same way
every time. `tests/test_frontend.py` checks that these files are byte-identical to the
official releases (their published SHA-384 hashes) and that no page loads anything from
the internet.
