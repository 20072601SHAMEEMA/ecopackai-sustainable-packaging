# End-to-End UI Test Report — EcoPackAI

**Date:** 2026-10-06 · **Tool:** Playwright 1.63.0 (Python) · **Browsers:** Chromium 153.0.8010.12,
Firefox 155.0 · **App:** Flask API + website started by the tests on a free local port
· **Tests:** `tests/e2e/test_ui_flows.py`, setup in `tests/e2e/conftest.py`

## 1. How to Run

```bash
pip install -r environments/requirements-dev.txt
python -m playwright install chromium firefox        # once: downloads the test browsers
pytest tests/e2e -v                                  # both browsers
set E2E_BROWSERS=firefox                             # Windows cmd: only one browser
pytest tests/e2e -v --junitxml=e2e_results.xml       # machine-readable report
```

The tests start the real app themselves (API, website, test database, client API key);
nothing has to be running beforehand. They are part of `pytest tests`, so CI runs them on
every push. Without Playwright installed they are skipped, not failed.

## 2. Results

**44 / 44 passed** (22 scenarios × 2 browsers). The full project suite (245 tests,
including these) passed on three consecutive complete runs: twice on SQLite and once on
PostgreSQL. The 9 Firefox tests that open the results page also passed 5 times in a row
after the scroll fix in section 5.

| Scenario | Chromium | Firefox |
|---|---|---|
| `test_navigation_reaches_every_page` | pass (2.5 s) | pass (10.2 s) |
| `test_empty_form_shows_errors_and_sends_nothing` | pass (1.2 s) | pass (2.7 s) |
| `test_invalid_values_get_specific_messages` | pass (1.4 s) | pass (2.8 s) |
| `test_loading_state_while_the_api_works` | pass (2.4 s) | pass (2.6 s) |
| `test_api_unreachable_shows_a_clear_message` | pass (0.8 s) | pass (2.0 s) |
| `test_server_error_shows_message_and_request_id` | pass (0.9 s) | pass (2.2 s) |
| `test_missing_api_key_is_explained` | pass (0.9 s) | pass (1.8 s) |
| `test_results_table_and_charts_match_the_api` | pass (2.4 s) | pass (3.9 s) |
| `test_chart_tooltips_and_legends_explain_the_values` | pass (3.5 s) | pass (5.6 s) |
| `test_csv_export_matches_the_screen` | pass (3.3 s) | pass (6.8 s) |
| `test_pdf_export_contains_the_summary` | pass (2.3 s) | pass (3.9 s) |
| `test_mode_switch_updates_table_and_charts` | pass (4.6 s) | pass (6.7 s) |
| `test_no_valid_material_is_explained` | pass (2.0 s) | pass (3.5 s) |
| `test_results_page_without_a_recommendation_shows_the_sample` | pass (0.8 s) | pass (1.6 s) |
| `test_tablet_layout_keeps_charts_visible_without_side_scrolling` | pass (2.5 s) | pass (4.1 s) |
| `test_no_javascript_errors_during_a_full_journey` | pass (2.4 s) | pass (4.8 s) |
| `test_results_appear_under_the_form_without_a_page_reload` | pass (3.5 s) | pass (4.5 s) |
| `test_top_pick_is_highlighted` | pass (1.3 s) | pass (1.9 s) |
| `test_table_columns_sort_both_ways [predicted_cost_usd]` | pass (3.7 s) | pass (6.8 s) |
| `test_table_columns_sort_both_ways [predicted_co2_per_kg]` | pass (3.4 s) | pass (7.2 s) |
| `test_full_results_page_table_is_sortable_too` | pass (2.8 s) | pass (5.8 s) |
| `test_incomplete_api_response_is_rejected` | pass (1.0 s) | pass (3.3 s) |

Whole project: **245 pytest tests** pass on SQLite and on PostgreSQL (this suite plus unit,
integration, database, report and frontend tests), plus **37 JavaScript unit tests** in Node
(validation, chart data, response check and table sorting).

## 3. Coverage Summary

### Critical user paths (from the task brief)

| Brief scenario | Covered by |
|---|---|
| Product input submission | every flow test fills the real form and clicks the real button |
| API invocation | `expect_response` on `POST /recommend` (status 200); routes stubbed only for failure tests |
| Recommendation table rendering | every cell equals the API response, under the form and on the results page |
| Chart visualization | chart data equals the API (labels, values, legend); tooltips; canvases have a real size |
| CSV/PDF export | real downloads; file names checked; CSV values equal the table; PDF text contains every material and score |
| Form validation errors | empty form, invalid values, live clearing of errors, 0 requests sent |
| Loading states | request held open: button disabled, spinner and "Ranking materials..." visible, then released |
| API failure handling | connection refused, HTTP 500 with request ID, missing API key (real 401) |
| Charts update on new predictions | `test_mode_switch_updates_table_and_charts`: new response → table and charts re-render; survives reload |
| Table updates without page reload | `test_results_appear_under_the_form_without_a_page_reload`: no navigation, page state kept, second submit updates the same table |
| Sorting and highlighting | cost and CO₂ columns sort both ways (`aria-sort`); results-page table sortable; top pick highlighted |
| Response schema consistency | `test_incomplete_api_response_is_rejected`: incomplete response is not shown or stored |
| Cross-browser | all scenarios in Chromium and Firefox |
| Screen sizes | 1280 px (all tests) and 768 px tablet (layout test) |

### Requirement coverage by layer

| Requirement | Unit / integration tests | End-to-end |
|---|---|---|
| Validation rules | 17 Node tests (`predict.test.js`) | 2 scenarios |
| Chart data | 7 Node tests (`charts.test.js`) | 3 scenarios |
| Export content and naming | 13 pytest tests (`test_reports.py`) | 2 scenarios |
| Response check and sorting | 13 Node tests (`recommendation_table.test.js`) | 5 scenarios |
| Frontend ↔ backend consistency | `test_frontend.py` (26 tests) | all flows |

**Not automated:** Safari/WebKit (not in the brief's browser list; Playwright supports it
via `E2E_BROWSERS=webkit` after `python -m playwright install webkit`), and mobile phone widths.

## 4. Failure Logging and Reproduction

When a test fails, `tests/e2e/artifacts/<test>_<browser>_/` receives:

| File | Content |
|---|---|
| `screenshot.png` | Full-page screenshot at the moment of failure |
| `page.html` | The page's HTML at that moment |
| `console.log` | Every browser console message and JavaScript error during the test |
| `trace.zip` | Playwright trace: each step with screenshots, DOM snapshots and network calls |

Replay a failure step by step with `python -m playwright show-trace tests/e2e/artifacts/<test>/trace.zip`,
or re-run one test with `pytest "tests/e2e/test_ui_flows.py::<test>[chromium]" -v`. Each
test uses a fresh browser context (no shared cookies or storage), so failures are
independent and reproducible. The artifacts folder is git-ignored.

This was verified by running a deliberately failing test: all four files were created.

## 5. Problems Found by the E2E Tests

| Problem | Cause | Fix |
|---|---|---|
| On a slow network, pages loaded without styles, charts or working buttons (11 of 30 tests failed) | Bootstrap and Chart.js came from a CDN; downloads failed or arrived incomplete and the browser refused them (integrity check) | Libraries shipped in `frontend/static/vendor/` (verified against the official hashes); a test now forbids internet-loaded files |
| "Response body not available" in Chromium | The page navigates to the results page right after the API answers, and Chromium discards the response body | The test reads the result the page stored (the exact data it rendered) |
| Clicking "API settings" sometimes missed | A validation message appearing on blur shifted the layout during the click | Test setup opens the section directly; the user flow itself was not affected |
| A Firefox run once failed to open the results page (1 of 245 tests) | The form page smooth-scrolls to the new results; the click on "View charts & export" landed while the page was still moving | The test waits for scrolling to stop before clicking (as a person would); the app now skips the animation for users with the "reduce motion" setting |
