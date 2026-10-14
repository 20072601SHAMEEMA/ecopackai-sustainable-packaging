"""
EcoPackAI - Frontend Tests
Module: Frontend UI

- The JavaScript validation tests (tests/frontend/predict.test.js) pass in Node.
- The form's allowed values and limits match what the backend accepts.
- Every form field has a label, an error slot and the right options.
- Pages are complete static files (load without the backend) and are also
  served by the Flask app.
- The sample result shown without a backend is real API output.

Run with: pytest tests/test_frontend.py -v
"""

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest
from conftest import ROOT

from recommendation.ranker import load_config
from routes.predict import CONFIG_FILE, FRAGILITY_RANGE, SHIPPING_TYPES

FRONTEND = ROOT / "frontend"
PAGES = ["index.html", "predict.html", "results.html", "dashboard.html"]
CONFIG = load_config(CONFIG_FILE)
PREDICT_JS = (FRONTEND / "static" / "js" / "predict.js").read_text(encoding="utf-8")


def js_rules():
    """Evaluate predict.js in Node and return its RULES object."""
    module = json.dumps(str(FRONTEND / "static" / "js" / "predict.js"))
    script = f"process.stdout.write(JSON.stringify(require({module}).RULES))"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")


class PageParser(HTMLParser):
    """Collects element ids, form fields, select options, labels and assets."""

    def __init__(self):
        super().__init__()
        self.ids, self.labels, self.scripts, self.styles = set(), set(), [], []
        self.fields, self.options, self._select = {}, {}, None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "label" and "for" in attrs:
            self.labels.add(attrs["for"])
        if tag in {"input", "select"} and "name" in attrs:
            self.fields[attrs["name"]] = attrs
        if tag == "select":
            self._select = attrs.get("name")
            self.options[self._select] = []
        if tag == "option" and self._select:
            self.options[self._select].append(attrs.get("value"))
        if tag == "script" and "src" in attrs:
            self.scripts.append(attrs)
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.styles.append(attrs)

    def handle_data(self, data):
        if self._select and self.options[self._select] and self.options[self._select][-1] is None:
            self.options[self._select][-1] = data.strip()      # <option>Food</option> has no value attribute

    def handle_endtag(self, tag):
        if tag == "select":
            self._select = None


def parse(page):
    parser = PageParser()
    parser.feed((FRONTEND / page).read_text(encoding="utf-8"))
    return parser


# ---- JavaScript unit tests ----

@needs_node
def test_javascript_unit_tests_pass():
    """Validation, chart data, response check and table sorting tests (tests/frontend/*.test.js)."""
    files = [str(ROOT / "tests" / "frontend" / name)
             for name in ("predict.test.js", "charts.test.js", "recommendation_table.test.js")]
    result = subprocess.run(["node", "--test", *files], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert re.search(r"^# fail 0$", result.stdout, re.M)


# ---- Frontend rules match the backend ----

@needs_node
def test_frontend_rules_match_backend():
    rules = js_rules()
    assert set(rules["category"]["options"]) == set(CONFIG["category_suitability"])
    assert rules["shipping_type"]["options"] == SHIPPING_TYPES
    assert (rules["fragility_index"]["min"], rules["fragility_index"]["max"]) == FRAGILITY_RANGE
    assert rules["mode"]["options"] == list(CONFIG["modes"])
    assert rules["mode"]["default"] == CONFIG["default_mode"]
    assert rules["top_n"]["default"] == CONFIG["top_n"]
    assert rules["top_n"]["max"] == 20                     # MAX_TOP_N in backend/settings.py
    assert rules["product_weight_kg"]["min"] == 0 and rules["product_weight_kg"]["minExclusive"]


def test_product_name_limit_matches_database_column():
    from models import Product
    assert f"maxLength: {Product.__table__.c.product_name.type.length}" in PREDICT_JS


@needs_node
def test_valid_frontend_payload_is_accepted_by_the_api(client):
    script = ("const F = require(" + json.dumps(str(FRONTEND / "static" / "js" / "predict.js")) + ");"
              "process.stdout.write(JSON.stringify(F.validateProduct({product_name: 'Smartphone', category: "
              "'Electronics', product_weight_kg: '0.3', fragility_index: '5', shipping_type: 'Air', "
              "mode: 'cost_first', top_n: '3'}).payload));")
    payload = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    from conftest import CLIENT
    response = client.post("/recommend", json=payload, headers=CLIENT)
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["result"] == "ok" and len(body["recommendations"]) == 3 and body["mode"] == "cost_first"


# ---- Form structure ----

@needs_node
def test_form_has_every_field_with_label_and_error_slot():
    page = parse("predict.html")
    for name in js_rules():
        assert name in page.fields, f"missing form field {name}"
        assert page.fields[name].get("id") == name
        assert name in page.labels, f"missing <label for='{name}'>"
        assert f"{name}-error" in page.ids, f"missing error slot {name}-error"
        assert f"{name}-error" in page.fields[name].get("aria-describedby", "")


@needs_node
def test_select_options_match_the_rules():
    page, rules = parse("predict.html"), js_rules()
    assert page.options["category"][1:] == rules["category"]["options"]       # first option = "Choose..."
    assert page.options["shipping_type"][1:] == rules["shipping_type"]["options"]
    assert page.options["fragility_index"][1:] == ["1", "2", "3", "4", "5"]
    assert page.options["mode"] == rules["mode"]["options"]


def test_form_uses_javascript_validation_and_status_areas():
    html = (FRONTEND / "predict.html").read_text(encoding="utf-8")
    assert '<form id="product-form"' in html and "novalidate" in html
    page = parse("predict.html")
    assert {"form-errors", "submit-status", "submit-button", "api-settings", "api-base", "api-key"} <= page.ids


def test_results_page_has_charts_mode_switch_and_exports():
    page = parse("results.html")
    assert {"chart-co2", "chart-cost", "chart-score", "export-csv", "export-pdf", "mode-switch",
            "action-status"} <= page.ids
    html = (FRONTEND / "results.html").read_text(encoding="utf-8")
    modes = re.findall(r'data-mode="([a-z_]+)"', html)
    assert modes == list(CONFIG["modes"])
    sources = [s["src"] for s in page.scripts]
    assert sources.index("static/js/charts.js") < sources.index("static/js/results.js")
    assert "static/vendor/chart-4.4.4.umd.js" in sources


def test_form_page_shows_results_inline_with_a_sortable_table():
    page = parse("predict.html")
    assert {"inline-results", "inline-summary", "inline-no-result", "inline-table", "inline-body",
            "open-full-results"} <= page.ids
    html = (FRONTEND / "predict.html").read_text(encoding="utf-8")
    columns = re.findall(r'data-sort="([a-z0-9_]+)"', html)
    assert columns == ["rank", "material_id", "packaging_type", "final_score", "predicted_cost_usd",
                       "predicted_co2_per_kg", "recyclability_percent"]
    sources = [s["src"] for s in page.scripts]
    assert sources.index("static/js/recommendation_table.js") < sources.index("static/js/predict.js")


def test_both_tables_use_the_same_sortable_columns():
    sort_keys = [re.findall(r'data-sort="([a-z0-9_]+)"', (FRONTEND / page).read_text(encoding="utf-8"))
                 for page in ("predict.html", "results.html")]
    assert sort_keys[0] == sort_keys[1]


# ---- Static pages ----

@pytest.mark.parametrize("page", PAGES)
def test_page_is_complete_and_uses_shared_layout(page):
    parsed = parse(page)
    html = (FRONTEND / page).read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and '<meta name="viewport"' in html
    assert {"site-header", "site-footer"} <= parsed.ids
    sources = [s["src"] for s in parsed.scripts]
    assert "static/js/layout.js" in sources
    for asset in parsed.scripts + parsed.styles:              # everything is served locally
        url = asset.get("src") or asset.get("href")
        assert not url.startswith(("http:", "https:", "//")), f"{page} loads {url} from the internet"
        assert (FRONTEND / url).is_file(), f"{page} references missing file {url}"


# Official Subresource Integrity hashes of the published library files
VENDOR_SHA384 = {
    "bootstrap-5.3.3.min.css": "QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH",
    "bootstrap-5.3.3.bundle.min.js": "YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz",
    "chart-4.4.4.umd.js": "G436+Z2nlA8+PNoeRvWdxKbvOf8E/y+lYxqht2iBwNHTQDV5CJr3+AGVj8fGZi5t",
}


@pytest.mark.parametrize("name", VENDOR_SHA384)
def test_vendor_files_are_the_official_releases(name):
    """Bootstrap and Chart.js ship with the project (no internet needed); they must be unmodified."""
    import base64
    import hashlib
    digest = base64.b64encode(hashlib.sha384((FRONTEND / "static" / "vendor" / name).read_bytes()).digest()).decode()
    assert digest == VENDOR_SHA384[name]


def test_scripts_never_write_raw_html():
    """Data is shown with textContent only, so it can never inject markup (XSS)."""
    unsafe = re.compile(r"\.\s*(innerHTML|outerHTML)\s*[+]?=|insertAdjacentHTML|document\.write")
    for script in (FRONTEND / "static" / "js").glob("*.js"):         # our code (vendor files excluded)
        assert not unsafe.search(script.read_text(encoding="utf-8")), script.name


# ---- Served by the backend ----

@pytest.mark.parametrize("page", PAGES)
def test_pages_are_served_by_flask(client, page):
    response = client.get(f"/{page}")
    assert response.status_code == 200 and response.mimetype == "text/html"
    assert response.get_data() == (FRONTEND / page).read_bytes()


def test_root_serves_home_page_and_static_files(client):
    assert client.get("/").get_data() == (FRONTEND / "index.html").read_bytes()
    js = client.get("/static/js/predict.js")
    assert js.status_code == 200 and "javascript" in js.mimetype


def test_unknown_pages_and_files_are_404(client):
    assert client.get("/secret.html").status_code == 404
    assert client.get("/static/js/missing.js").status_code == 404
    assert client.get("/static/../backend/app.py").status_code == 404


def test_api_routes_are_unchanged(client):
    assert client.get("/predict").status_code == 405           # API route, not a page
    assert client.get("/health").get_json()["status"] == "ok"


# ---- Sample result ----

def test_sample_result_is_real_api_output(client):
    text = (FRONTEND / "static" / "js" / "sample_result.js").read_text(encoding="utf-8")
    sample = json.loads(re.search(r"window\.ECOPACK_SAMPLE_RESULT = (\{.*\});", text, re.S).group(1))
    from conftest import CLIENT
    live = client.post("/recommend", json={"product": sample["product"],
                                           "options": {"mode": sample["mode"], "top_n": sample["top_n"]}},
                       headers=CLIENT).get_json()
    assert live["recommendations"] == sample["recommendations"]
    assert live["n_candidates"] == sample["n_candidates"]
