"""
EcoPackAI - Report Export Tests
Module: Frontend Analytics & Reporting

GET /reports/<run_id>.csv and .pdf: content equals the /recommend response,
naming convention, authentication, missing runs, runs without results.

Run with: pytest tests/test_reports.py -v
"""

import csv
import io
import re

import pytest
from conftest import CLIENT, MATERIALS
from pypdf import PdfReader

from routes.reports import CSV_COLUMNS

PRODUCT = {"product_name": "Crème Brûlée Jar", "category": "Food", "product_weight_kg": 0.5,
           "fragility_index": 2, "shipping_type": "Air"}
NAME_PATTERN = r'attachment; filename="ecopackai_{kind}_{slug}_\d{{8}}-\d{{6}}_run{run}\.{ext}"'


@pytest.fixture(scope="module")
def run(client):
    body = client.post("/recommend", json={"product": PRODUCT, "options": {"mode": "cost_first", "top_n": 5}},
                       headers=CLIENT).get_json()
    assert body["status"] == "success"
    return body


def csv_rows(response):
    assert response.data.startswith(b"\xef\xbb\xbf")                 # UTF-8 BOM for Excel
    return list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))


def pdf_text(response):
    reader = PdfReader(io.BytesIO(response.data))
    return "\n".join(page.extract_text() for page in reader.pages)


# ---- CSV ----

def test_csv_matches_the_recommendation(client, run):
    response = client.get(f"/reports/{run['run_id']}.csv", headers=CLIENT)
    assert response.status_code == 200 and response.mimetype == "text/csv"
    rows = csv_rows(response)
    assert list(rows[0]) == CSV_COLUMNS
    assert len(rows) == len(run["recommendations"])
    for row, item in zip(rows, run["recommendations"]):
        assert int(row["rank"]) == item["rank"] and row["material_id"] == item["material_id"]
        assert row["material_type"] == item["material_type"] and row["packaging_type"] == item["packaging_type"]
        for field in ("final_score", "predicted_cost_usd", "predicted_co2_per_kg", "recyclability_percent"):
            assert float(row[field]) == pytest.approx(item[field], abs=1e-9), field
        assert row["product_name"] == PRODUCT["product_name"] and row["mode"] == "cost_first"
        assert int(row["run_id"]) == run["run_id"]


def test_csv_material_details_come_from_the_catalogue(client, run):
    rows = csv_rows(client.get(f"/reports/{run['run_id']}.csv", headers=CLIENT))
    catalogue = MATERIALS.set_index("material_id")
    for row in rows:
        assert float(row["recyclability_percent"]) == catalogue.loc[row["material_id"], "recyclability_percent"]


def test_csv_file_name_convention(client, run):
    response = client.get(f"/reports/{run['run_id']}.csv", headers=CLIENT)
    pattern = NAME_PATTERN.format(kind="recommendations", slug="creme-brulee-jar", run=run["run_id"], ext="csv")
    assert re.fullmatch(pattern, response.headers["Content-Disposition"])


# ---- PDF ----

def test_pdf_is_valid_and_contains_the_results(client, run):
    response = client.get(f"/reports/{run['run_id']}.pdf", headers=CLIENT)
    assert response.status_code == 200 and response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")
    text = pdf_text(response)
    best = run["recommendations"][0]
    assert "Sustainability Summary" in text and "Crème Brûlée Jar" in text and "Cost first" in text
    assert f"{best['material_id']} - {best['packaging_type']}" in text
    for item in run["recommendations"]:
        assert item["material_id"] in text
        assert f"{item['final_score']:.1f}" in text
        assert f"${item['predicted_cost_usd']:.2f}" in text
        assert f"{item['predicted_co2_per_kg']:.3f}" in text


def test_pdf_file_name_convention(client, run):
    response = client.get(f"/reports/{run['run_id']}.pdf", headers=CLIENT)
    pattern = NAME_PATTERN.format(kind="sustainability_summary", slug="creme-brulee-jar", run=run["run_id"],
                                  ext="pdf")
    assert re.fullmatch(pattern, response.headers["Content-Disposition"])


# ---- Edge cases ----

def test_run_without_results(client):
    body = client.post("/recommend", json={"product_id": 775}, headers=CLIENT).get_json()   # wine bottle by sea
    rows = csv_rows(client.get(f"/reports/{body['run_id']}.csv", headers=CLIENT))
    assert rows == []
    text = pdf_text(client.get(f"/reports/{body['run_id']}.pdf", headers=CLIENT))
    assert "No material in the catalogue meets all constraints" in text


def test_database_product_export_uses_product_name(client):
    body = client.post("/recommend", json={"product_id": 2, "options": {"top_n": 2}}, headers=CLIENT).get_json()
    response = client.get(f"/reports/{body['run_id']}.csv", headers=CLIENT)
    assert "_smartphone_" in response.headers["Content-Disposition"]
    assert [r["material_id"] for r in csv_rows(response)] == [x["material_id"] for x in body["recommendations"]]


def test_unnamed_product_gets_a_default_file_name(client):
    product = {k: v for k, v in PRODUCT.items() if k != "product_name"}
    body = client.post("/recommend", json={"product": product}, headers=CLIENT).get_json()
    assert "_product_" in client.get(f"/reports/{body['run_id']}.csv", headers=CLIENT).headers["Content-Disposition"]


@pytest.mark.parametrize("extension", ["csv", "pdf"])
def test_exports_need_an_api_key(client, run, extension):
    assert client.get(f"/reports/{run['run_id']}.{extension}").status_code == 401


@pytest.mark.parametrize("extension", ["csv", "pdf"])
def test_unknown_run_is_404(client, extension):
    response = client.get(f"/reports/987654.{extension}", headers=CLIENT)
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "not_found"


def test_other_extensions_are_not_served(client, run):
    assert client.get(f"/reports/{run['run_id']}.xlsx", headers=CLIENT).status_code == 404
