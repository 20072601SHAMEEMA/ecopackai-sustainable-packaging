"""
EcoPackAI - End-to-End UI Tests (Playwright, Chromium + Firefox)
Module: Frontend Quality Assurance

Each test drives a real browser against the running app (API + website):
product input -> validation -> API call -> results table under the form (no page
reload, sortable, response checked) -> charts -> CSV/PDF export, plus loading
states, API failures, mode switching and layout.

Run with: pytest tests/e2e -v            (both browsers)
          E2E_BROWSERS=firefox pytest tests/e2e -v
"""

import csv
import io
import json
import re

import pytest
from pypdf import PdfReader

pytestmark = pytest.mark.e2e

CHOCOLATE_BOX = {"product_name": "Chocolate Box", "category": "Food", "product_weight_kg": "0.5",
                 "fragility_index": "2", "shipping_type": "Air"}


# ---------------------------------------------------------------- helpers

def fill_form(page, values, key="default"):
    page.goto("/predict.html")
    for name, value in values.items():
        field = page.locator(f"#{name}")
        if field.evaluate("el => el.tagName") == "SELECT":
            field.select_option(value)
        else:
            field.fill(value)
    if key == "default":
        key = page.e2e_key                     # the client key the test server accepts (tests/e2e/conftest.py)
    if key is not None:
        # open "API settings" directly: a click can miss when a field's error message shifts the layout
        page.locator("#api-settings").evaluate("details => { details.open = true; }")
        page.locator("#api-key").fill(key)


def received_result(page):
    """The /recommend response exactly as the browser received and stored it (sessionStorage).

    (Chromium discards a response body once the page navigates away, so it is read from here.)"""
    return page.evaluate("() => JSON.parse(sessionStorage.getItem('ecopackai:lastResult'))")


def submit_and_show_inline(page):
    """Submit the form; wait until the results appear under it (same page). Returns the API response."""
    with page.expect_response(lambda r: r.url.endswith("/recommend") and r.request.method == "POST") as info:
        page.locator("#submit-button").click()
    assert info.value.status == 200
    page.locator("#inline-results").wait_for(state="visible")
    assert page.url.endswith("/predict.html")
    return info.value.json()


def wait_for_scroll_to_settle(page):
    """The page smooth-scrolls to the results; wait until it stops before clicking (as a person would)."""
    page.wait_for_function("""() => new Promise(done => {
        let last = window.scrollY, still = 0;
        (function check() {
            if (window.scrollY === last) { still += 1; } else { still = 0; last = window.scrollY; }
            if (still >= 5) { done(true); } else { requestAnimationFrame(check); }
        })();
    })""")


def submit_and_wait_for_results(page):
    """Submit the form, then open the full analysis page; return the response the browser stored."""
    submit_and_show_inline(page)
    wait_for_scroll_to_settle(page)
    with page.expect_navigation(url="**/results.html"):
        page.locator("#open-full-results").click()
    wait_for_charts(page)
    return received_result(page)


def wait_for_charts(page):
    page.wait_for_function("() => window.EcoPackCharts && Object.keys(window.EcoPackCharts.snapshot()).length === 3")


def table_rows(page, body="#results-body"):
    rows = []
    for row in page.locator(f"{body} tr").all():
        cells = [c.inner_text().strip() for c in row.locator("td").all()]
        rows.append({"rank": cells[0], "material_id": cells[1].splitlines()[0], "packaging_type": cells[2],
                     "score": cells[3].split()[-1], "cost": cells[4], "co2": cells[5], "recyclable": cells[6]})
    return rows


def expected_rows(response):
    return [{"rank": f"#{r['rank']}", "material_id": r["material_id"], "packaging_type": r["packaging_type"],
             "score": f"{r['final_score']:.1f}", "cost": f"${r['predicted_cost_usd']:.2f}",
             "co2": f"{r['predicted_co2_per_kg']:.3f}", "recyclable": f"{r['recyclability_percent']:.0f}%"}
            for r in response["recommendations"]]


def assert_charts_match(page, response):
    snapshot = page.evaluate("() => window.EcoPackCharts.snapshot()")
    recs = response["recommendations"]
    labels = [f"#{r['rank']} {r['material_id']}" for r in recs]
    for key, field in (("co2", "predicted_co2_per_kg"), ("cost", "predicted_cost_usd"), ("score", "final_score")):
        assert snapshot[key]["labels"] == labels, key
        assert snapshot[key]["values"] == [r[field] for r in recs], key
        assert snapshot[key]["legend"] == list(dict.fromkeys(r["packaging_type"] for r in recs)), key


def recommend_requests(page):
    calls = []
    page.on("request", lambda req: calls.append(req.url) if req.url.endswith("/recommend") else None)
    return calls


# ---------------------------------------------------------------- navigation

def test_navigation_reaches_every_page(page):
    page.goto("/")
    for label, path, heading in (("Get Recommendation", "/predict.html", "Describe your product"),
                                 ("Results", "/results.html", "Recommended packaging"),
                                 ("Analytics", "/dashboard.html", "Analytics"),
                                 ("Home", "/index.html", "Choose greener packaging")):
        page.get_by_role("link", name=label, exact=True).first.click()
        page.wait_for_url(f"**{path}")
        assert heading in page.locator("h1").inner_text()
        assert page.locator(".nav-link.active").inner_text() == label


# ---------------------------------------------------------------- form validation

def test_empty_form_shows_errors_and_sends_nothing(page):
    calls = recommend_requests(page)
    page.goto("/predict.html")
    page.locator("#submit-button").click()
    summary = page.locator("#form-errors")
    assert summary.is_visible() and "Please fix 5 problems" in summary.inner_text()
    for field in ("product_name", "category", "product_weight_kg", "fragility_index", "shipping_type"):
        assert "is-invalid" in page.locator(f"#{field}").get_attribute("class")
        assert page.locator(f"#{field}-error").inner_text().endswith("is required.")
    assert page.evaluate("document.activeElement.id") == "product_name"
    page.wait_for_timeout(500)
    assert calls == []


def test_invalid_values_get_specific_messages(page):
    calls = recommend_requests(page)
    fill_form(page, {**CHOCOLATE_BOX, "product_name": "A", "product_weight_kg": "12kg", "top_n": "50"})
    page.locator("#submit-button").click()
    assert page.locator("#product_name-error").inner_text() == "Product name must be at least 2 characters."
    assert page.locator("#product_weight_kg-error").inner_text() == "Weight (kg) must be a number."
    assert page.locator("#top_n-error").inner_text() == "Number of recommendations must be at most 20."
    assert page.locator(".is-invalid").count() == 3
    page.locator("#product_weight_kg").fill("0.5")                  # error clears while typing
    assert "is-invalid" not in page.locator("#product_weight_kg").get_attribute("class")
    page.wait_for_timeout(300)
    assert calls == []


# ---------------------------------------------------------------- loading and failures

def test_loading_state_while_the_api_works(page):
    held = []
    page.route("**/recommend", lambda route: held.append(route))
    fill_form(page, CHOCOLATE_BOX)
    page.locator("#submit-button").click()
    page.wait_for_function("() => document.querySelector('#submit-button').disabled")
    assert page.locator("#submit-button .spinner-border").is_visible()
    assert "Ranking materials" in page.locator("#submit-status").inner_text()
    page.wait_for_function("() => true")                           # let the route handler run
    assert len(held) == 1
    held[0].continue_()
    page.locator("#inline-results").wait_for(state="visible")
    assert not page.locator("#submit-button").is_disabled()


def test_api_unreachable_shows_a_clear_message(page):
    page.route("**/recommend", lambda route: route.abort("connectionrefused"))
    fill_form(page, CHOCOLATE_BOX)
    page.locator("#submit-button").click()
    status = page.locator("#submit-status")
    status.wait_for(state="visible")
    assert "Cannot reach the EcoPackAI API" in status.inner_text()
    assert page.url.endswith("/predict.html")
    assert not page.locator("#submit-button").is_disabled()        # user can try again


def test_server_error_shows_message_and_request_id(page):
    error = {"status": "error", "request_id": "e2e-failure-01",
             "error": {"code": "internal_error", "message": "Unexpected server error."}}
    page.route("**/recommend", lambda route: route.fulfill(status=500, content_type="application/json",
                                                           body=json.dumps(error)))
    fill_form(page, CHOCOLATE_BOX)
    page.locator("#submit-button").click()
    status = page.locator("#submit-status")
    status.wait_for(state="visible")
    assert "Unexpected server error." in status.inner_text() and "e2e-failure-01" in status.inner_text()


def test_missing_api_key_is_explained(page):
    fill_form(page, CHOCOLATE_BOX, key=None)
    page.locator("#submit-button").click()
    status = page.locator("#submit-status")
    status.wait_for(state="visible")
    assert "needs a valid client key" in status.inner_text()
    assert page.locator("#api-settings").get_attribute("open") is not None
    assert page.evaluate("document.activeElement.id") == "api-key"


# ---------------------------------------------------------------- results, charts, exports

def test_results_table_and_charts_match_the_api(page):
    fill_form(page, CHOCOLATE_BOX)
    response = submit_and_wait_for_results(page)
    assert response["result"] == "ok" and len(response["recommendations"]) == 5
    assert not page.locator("#sample-notice").is_visible()
    assert table_rows(page) == expected_rows(response)
    best = response["recommendations"][0]
    assert page.locator("#best-material").inner_text() == f"{best['material_id']} — {best['packaging_type']}"
    assert_charts_match(page, response)
    for canvas in ("#chart-co2", "#chart-cost", "#chart-score"):
        box = page.locator(canvas).bounding_box()
        assert box and box["width"] > 200 and box["height"] > 150
    assert page.locator("#mode-switch [data-mode='balanced']").get_attribute("aria-pressed") == "true"


def hover_bar(page, canvas, index):
    """Move the mouse onto bar <index> of a chart and return the tooltip lines (None if no tooltip)."""
    page.locator(f"#{canvas}").scroll_into_view_if_needed()
    page.wait_for_timeout(400)                                    # chart animation
    pos = page.evaluate("""([id, i]) => { const c = Chart.getChart(id);
        const meta = c.getDatasetMeta(c.data.datasets.findIndex(d => d.data[i] !== null));
        const p = meta.data[i].getCenterPoint(); const r = c.canvas.getBoundingClientRect();
        return {x: r.left + p.x, y: r.top + p.y}; }""", [canvas, index])
    page.mouse.move(pos["x"], pos["y"])
    page.wait_for_function("id => Chart.getChart(id).tooltip.opacity > 0", arg=canvas)
    return page.evaluate("""id => { const t = Chart.getChart(id).tooltip;
        return [t.title, t.body.map(b => b.lines), t.body.map(b => b.after)].flat(3); }""", canvas)


def test_chart_tooltips_and_legends_explain_the_values(page):
    fill_form(page, CHOCOLATE_BOX)
    response = submit_and_wait_for_results(page)
    first, fourth = response["recommendations"][0], response["recommendations"][3]
    co2_line = f"{fourth['packaging_type']}: {fourth['predicted_co2_per_kg']:.3f} kg CO₂ per kg"
    cost_line = f"{first['packaging_type']}: ${first['predicted_cost_usd']:.2f} per unit"
    assert hover_bar(page, "chart-co2", 3) == [f"#4 {fourth['material_id']}", co2_line]
    assert hover_bar(page, "chart-cost", 0) == [f"#1 {first['material_id']}", cost_line]
    lines = hover_bar(page, "chart-score", 0)
    assert lines[:2] == [f"#1 {first['material_id']}", f"{first['packaging_type']}: {first['final_score']:.1f} / 100"]
    assert lines[2] == f"CO₂ score {round(first['scores']['co2'] * 100)}%"
    assert len(lines) == 6
    legend = page.evaluate("() => Chart.getChart('chart-co2').legend.legendItems.map(i => i.text)")
    assert legend == list(dict.fromkeys(r["packaging_type"] for r in response["recommendations"]))


def test_csv_export_matches_the_screen(page):
    fill_form(page, CHOCOLATE_BOX)
    response = submit_and_wait_for_results(page)
    with page.expect_download() as info:
        page.locator("#export-csv").click()
    download = info.value
    assert re.fullmatch(rf"ecopackai_recommendations_chocolate-box_\d{{8}}-\d{{6}}_run{response['run_id']}\.csv",
                        download.suggested_filename)
    rows = list(csv.DictReader(io.StringIO(open(download.path(), encoding="utf-8-sig").read())))
    screen = table_rows(page)
    assert len(rows) == len(screen) == 5
    for row, shown, item in zip(rows, screen, response["recommendations"]):
        assert f"#{row['rank']}" == shown["rank"] and row["material_id"] == shown["material_id"]
        assert row["packaging_type"] == shown["packaging_type"]
        assert f"{float(row['final_score']):.1f}" == shown["score"]
        assert f"${float(row['predicted_cost_usd']):.2f}" == shown["cost"]
        assert f"{float(row['predicted_co2_per_kg']):.3f}" == shown["co2"]
        assert float(row["final_score"]) == pytest.approx(item["final_score"], abs=1e-9)
    assert "Downloaded" in page.locator("#action-status").inner_text()


def test_pdf_export_contains_the_summary(page):
    fill_form(page, CHOCOLATE_BOX)
    response = submit_and_wait_for_results(page)
    with page.expect_download() as info:
        page.locator("#export-pdf").click()
    download = info.value
    assert re.fullmatch(rf"ecopackai_sustainability_summary_chocolate-box_\d{{8}}-\d{{6}}_run{response['run_id']}"
                        r"\.pdf", download.suggested_filename)
    with open(download.path(), "rb") as f:
        data = f.read()
    assert data.startswith(b"%PDF-")
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
    assert "Chocolate Box" in text and "Sustainability Summary" in text
    for item in response["recommendations"]:
        assert item["material_id"] in text and f"{item['final_score']:.1f}" in text


def test_mode_switch_updates_table_and_charts(page):
    fill_form(page, CHOCOLATE_BOX)
    first = submit_and_wait_for_results(page)
    with page.expect_response(lambda r: r.url.endswith("/recommend")) as info:
        page.locator("#mode-switch [data-mode='cost_first']").click()
    second = info.value.json()
    page.wait_for_function("() => document.querySelector(\"[data-mode='cost_first']\").getAttribute('aria-pressed')"
                           " === 'true'")
    assert second["mode"] == "cost_first" and second["recommendations"] != first["recommendations"]
    assert table_rows(page) == expected_rows(second)
    assert_charts_match(page, second)
    assert "Cost first" in page.locator("#product-summary").inner_text()
    assert "Updated" in page.locator("#action-status").inner_text()
    page.reload()                                                    # the new result is remembered
    wait_for_charts(page)
    assert table_rows(page) == expected_rows(second)


def test_no_valid_material_is_explained(page):
    fill_form(page, {"product_name": "Wine Bottle", "category": "Drinkware", "product_weight_kg": "1.34",
                     "fragility_index": "4", "shipping_type": "Sea"})
    response = submit_and_show_inline(page)
    assert response["result"] == "no_valid_material"
    assert page.locator("#inline-no-result").is_visible()           # under the form
    assert not page.locator("#inline-table-card").is_visible()
    wait_for_scroll_to_settle(page)
    with page.expect_navigation(url="**/results.html"):             # and on the full results page
        page.locator("#open-full-results").click()
    page.locator("#product-summary dt").first.wait_for()
    assert page.locator("#no-result").is_visible()
    assert not page.locator("#results-section").is_visible()


def test_results_page_without_a_recommendation_shows_the_sample(page):
    page.goto("/results.html")
    wait_for_charts(page)
    assert page.locator("#sample-notice").is_visible()
    assert page.locator("#results-body tr").count() == 5
    sample = page.evaluate("() => window.ECOPACK_SAMPLE_RESULT")
    assert_charts_match(page, sample)
    assert page.locator("#export-csv").is_disabled() and page.locator("#export-pdf").is_disabled()


def test_tablet_layout_keeps_charts_visible_without_side_scrolling(page):
    page.set_viewport_size({"width": 768, "height": 1024})
    fill_form(page, CHOCOLATE_BOX)
    submit_and_wait_for_results(page)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    for canvas in ("#chart-co2", "#chart-cost", "#chart-score"):
        page.locator(canvas).scroll_into_view_if_needed()
        assert page.locator(canvas).is_visible()


def test_no_javascript_errors_during_a_full_journey(page):
    fill_form(page, CHOCOLATE_BOX)
    submit_and_wait_for_results(page)
    with page.expect_download():
        page.locator("#export-csv").click()
    errors = [line for line in page.console_log if line.startswith(("[error]", "[pageerror]"))]
    assert errors == []


# ---------------------------------------------------------------- frontend <-> backend integration

def test_results_appear_under_the_form_without_a_page_reload(page):
    navigations = []
    page.on("framenavigated", lambda frame: navigations.append(frame.url) if frame == page.main_frame else None)
    fill_form(page, CHOCOLATE_BOX)
    page.evaluate("() => { window.__sameDocument = true; }")       # disappears if the page reloads
    navigations.clear()
    response = submit_and_show_inline(page)
    assert page.evaluate("() => window.__sameDocument === true") and navigations == []
    assert table_rows(page, "#inline-body") == expected_rows(response)
    assert "Chocolate Box" in page.locator("#inline-summary").inner_text()
    assert "Ranked 5 materials" in page.locator("#submit-status").inner_text()

    # submit again with another mode: the same table updates, still no reload
    page.locator("#mode").select_option("cost_first")
    second = submit_and_show_inline(page)
    assert second["mode"] == "cost_first" and second["recommendations"] != response["recommendations"]
    assert table_rows(page, "#inline-body") == expected_rows(second)
    assert page.evaluate("() => window.__sameDocument === true") and navigations == []


def test_top_pick_is_highlighted(page):
    fill_form(page, CHOCOLATE_BOX)
    response = submit_and_show_inline(page)
    first_row = page.locator("#inline-body tr").first
    assert "top-pick" in first_row.get_attribute("class")
    assert "Top pick" in first_row.inner_text()
    assert page.locator("#inline-body tr.top-pick").count() == 1
    assert response["recommendations"][0]["material_id"] in first_row.inner_text()


@pytest.mark.parametrize("key", ["predicted_cost_usd", "predicted_co2_per_kg"])
def test_table_columns_sort_both_ways(page, key):
    fill_form(page, CHOCOLATE_BOX)
    response = submit_and_show_inline(page)
    header = page.locator(f"#inline-table th[data-sort='{key}']")
    header.locator("button").click()
    ascending = sorted(response["recommendations"], key=lambda r: (r[key], r["rank"]))
    assert [r["material_id"] for r in table_rows(page, "#inline-body")] == [r["material_id"] for r in ascending]
    assert header.get_attribute("aria-sort") == "ascending"
    header.locator("button").click()
    descending = sorted(response["recommendations"], key=lambda r: (-r[key], r["rank"]))
    assert [r["material_id"] for r in table_rows(page, "#inline-body")] == [r["material_id"] for r in descending]
    assert header.get_attribute("aria-sort") == "descending"
    # values in each row are unchanged by sorting
    by_rank = sorted(table_rows(page, "#inline-body"), key=lambda r: int(r["rank"].lstrip("#")))
    assert by_rank == expected_rows(response)


def test_full_results_page_table_is_sortable_too(page):
    fill_form(page, CHOCOLATE_BOX)
    response = submit_and_wait_for_results(page)
    page.locator("#results-table th[data-sort='final_score'] button").click()
    scores = [float(r["score"]) for r in table_rows(page)]
    assert scores == sorted(scores, reverse=True)
    assert page.locator("#results-table th[data-sort='final_score']").get_attribute("aria-sort") == "descending"
    assert_charts_match(page, response)                              # charts keep rank order


def test_incomplete_api_response_is_rejected(page):
    broken = {"status": "success", "request_id": "e2e-broken-01", "mode": "balanced", "result": "ok",
              "product": {"category": "Food"}, "recommendations": [{"rank": 1, "material_id": "MAT_0154"}]}
    page.route("**/recommend", lambda route: route.fulfill(status=200, content_type="application/json",
                                                           body=json.dumps(broken)))
    fill_form(page, CHOCOLATE_BOX)
    page.locator("#submit-button").click()
    page.wait_for_function("() => document.querySelector('#submit-status').innerText.includes('incomplete')")
    assert "e2e-broken-01" in page.locator("#submit-status").inner_text()
    assert not page.locator("#inline-results").is_visible()
    assert page.evaluate("() => sessionStorage.getItem('ecopackai:lastResult')") is None
