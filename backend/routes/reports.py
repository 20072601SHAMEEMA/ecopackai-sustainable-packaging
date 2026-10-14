"""
EcoPackAI - Report Export Endpoints
Module: Frontend Analytics & Reporting

GET /reports/<run_id>.csv  - recommendation results of one /recommend call (CSV)
GET /reports/<run_id>.pdf  - sustainability summary of the same call (PDF)

Both are built from the saved run (recommendation_runs + recommendation_logs,
joined with materials), so an export always contains exactly the numbers the
API returned and the results page displayed. Needs a client API key.

File names: ecopackai_recommendations_<product>_<YYYYMMDD-HHMMSS>_run<id>.csv
            ecopackai_sustainability_summary_<product>_<YYYYMMDD-HHMMSS>_run<id>.pdf
(timestamp = when the recommendation was made, UTC)
"""

import csv
import io
import re
import unicodedata
from datetime import timezone

from flask import Blueprint, Response
from fpdf import FPDF
from sqlalchemy import select

from middleware.auth import require_auth
from models import Material, RecommendationLog, RecommendationRun
from routes.common import components, error

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

MODE_LABELS = {"balanced": "Balanced", "sustainability_first": "Sustainability first", "cost_first": "Cost first"}
CSV_COLUMNS = ["run_id", "recommended_at_utc", "product_name", "category", "product_weight_kg", "fragility_index",
               "shipping_type", "mode", "rank", "material_id", "material_type", "packaging_type", "final_score",
               "predicted_cost_usd", "predicted_co2_per_kg", "recyclability_percent"]


def load_report(run_id: int):
    """The run plus its ranked materials, or None if the run does not exist."""
    with components().db.session() as session:
        run = session.get(RecommendationRun, run_id)
        if run is None:
            return None
        rows = session.execute(
            select(RecommendationLog, Material)
            .join(Material, Material.material_id == RecommendationLog.recommended_material_id)
            .where(RecommendationLog.run_id == run_id)
            .order_by(RecommendationLog.material_rank)
        ).all()
        created = run.created_at if run.created_at.tzinfo else run.created_at.replace(tzinfo=timezone.utc)
        return {
            "run_id": run.run_id,
            "created_at": created.astimezone(timezone.utc),
            "product": dict(run.product_snapshot),
            "mode": run.mode,
            "top_n": run.top_n,
            "n_candidates": run.n_candidates,
            "status": run.status,
            "models": {"cost": run.cost_model_version, "co2": run.co2_model_version},
            "request_id": run.request_id,
            "items": [{
                "rank": log.material_rank, "material_id": log.recommended_material_id,
                "material_type": material.material_type, "packaging_type": material.packaging_type,
                "final_score": log.final_score, "predicted_cost_usd": log.cost_prediction,
                "predicted_co2_per_kg": log.co2_prediction, "recyclability_percent": material.recyclability_percent,
            } for log, material in rows],
        }


def file_name(kind: str, report: dict, extension: str) -> str:
    name = unicodedata.normalize("NFKD", str(report["product"].get("product_name") or ""))
    ascii_name = name.encode("ascii", "ignore").decode("ascii")          # "Crème Brûlée" -> "Creme Brulee"
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:40]
    stamp = report["created_at"].strftime("%Y%m%d-%H%M%S")
    return f"ecopackai_{kind}_{slug or 'product'}_{stamp}_run{report['run_id']}.{extension}"


def download(content: bytes, mimetype: str, name: str) -> Response:
    response = Response(content, mimetype=mimetype)
    response.headers["Content-Disposition"] = f'attachment; filename="{name}"'
    response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
    return response


@reports_bp.get("/<int:run_id>.csv")
@require_auth("client")
def export_csv(run_id):
    report = load_report(run_id)
    if report is None:
        return error(404, "not_found", f"No recommendation run with run_id {run_id}.")
    product = report["product"]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for item in report["items"]:
        writer.writerow([report["run_id"], report["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                         product.get("product_name", ""), product.get("category"), product.get("product_weight_kg"),
                         product.get("fragility_index"), product.get("shipping_type"), report["mode"]]
                        + [item[c] for c in CSV_COLUMNS[8:]])
    # UTF-8 with BOM so Excel shows product names with accents correctly
    return download(buffer.getvalue().encode("utf-8-sig"), "text/csv", file_name("recommendations", report, "csv"))


@reports_bp.get("/<int:run_id>.pdf")
@require_auth("client")
def export_pdf(run_id):
    report = load_report(run_id)
    if report is None:
        return error(404, "not_found", f"No recommendation run with run_id {run_id}.")
    service = components().service.load()
    catalogue_avg_co2 = float(service.catalogue["predicted_co2_per_kg"].mean())
    content = bytes(build_pdf(report, catalogue_avg_co2).output())
    return download(content, "application/pdf", file_name("sustainability_summary", report, "pdf"))


# ---------------------------------------------------------------------------
# PDF layout
# ---------------------------------------------------------------------------

GREEN = (31, 122, 77)
GREY = (90, 100, 95)


def _latin1(text) -> str:
    """The built-in PDF fonts cover Latin-1 only; replace anything else instead of failing."""
    return str(text).encode("latin-1", "replace").decode("latin-1")


class SummaryPDF(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(*GREY)
        self.cell(0, 6, f"EcoPackAI sustainability summary  -  page {self.page_no()}", align="C")


def build_pdf(report: dict, catalogue_avg_co2: float) -> FPDF:
    pdf = SummaryPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_title("EcoPackAI sustainability summary")
    pdf.set_author("EcoPackAI")
    width = pdf.w - pdf.l_margin - pdf.r_margin
    product, items = report["product"], report["items"]

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 10, "EcoPackAI - Sustainability Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, _latin1(f"Recommendation run {report['run_id']}  |  made {report['created_at']:%Y-%m-%d %H:%M} UTC"
                           f"  |  request {report['request_id']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    _heading(pdf, "Product")
    details = [("Product", product.get("product_name") or "(unnamed)"), ("Category", product.get("category")),
               ("Weight", f"{product.get('product_weight_kg')} kg"),
               ("Fragility", f"{product.get('fragility_index')} / 5"), ("Shipping", product.get("shipping_type")),
               ("Ranking mode", MODE_LABELS.get(report["mode"], report["mode"])),
               ("Materials that passed the constraints", report["n_candidates"])]
    for label, value in details:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(70, 6, _latin1(label))
        pdf.set_font("Helvetica", size=10)
        pdf.cell(0, 6, _latin1(value), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    if not items:
        _heading(pdf, "Result")
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, "No material in the catalogue meets all constraints for this product (for example, "
                             "fragile items shipped by sea need cushioning that also resists moisture). Try a "
                             "different shipping type or fragility.")
        return pdf

    best = items[0]
    avg_co2 = sum(i["predicted_co2_per_kg"] for i in items) / len(items)
    _heading(pdf, "Best choice")
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 7, _latin1(f"{best['material_id']} - {best['packaging_type']} ({best['material_type']})"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 6, f"Score {best['final_score']:.1f} / 100   |   ${best['predicted_cost_usd']:.2f} per unit   |   "
                   f"{best['predicted_co2_per_kg']:.3f} kg CO2 per kg   |   "
                   f"{best['recyclability_percent']:.0f}% recyclable",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    _heading(pdf, "Sustainability summary")
    pdf.set_font("Helvetica", size=10)
    change = (avg_co2 - catalogue_avg_co2) / catalogue_avg_co2 * 100
    lines = [
        f"Average predicted CO2 of these {len(items)} materials: {avg_co2:.3f} kg per kg "
        f"({change:+.0f}% vs. catalogue average {catalogue_avg_co2:.3f}).",
        f"Predicted cost range: ${min(i['predicted_cost_usd'] for i in items):.2f} - "
        f"${max(i['predicted_cost_usd'] for i in items):.2f} per unit.",
        f"Recyclability: {min(i['recyclability_percent'] for i in items):.0f}% - "
        f"{max(i['recyclability_percent'] for i in items):.0f}%.",
    ]
    for line in lines:
        pdf.cell(0, 6, _latin1("- " + line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    _heading(pdf, "Recommended materials")
    columns = [("Rank", 12, "C"), ("Material", 24, "L"), ("Type", 26, "L"), ("Packaging type", 52, "L"),
               ("Score", 18, "R"), ("Cost/unit", 20, "R"), ("CO2/kg", 18, "R"), ("Recycl.", 16, "R")]
    scale = width / sum(c[1] for c in columns)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(232, 244, 238)
    for title, w, align in columns:
        pdf.cell(w * scale, 7, title, border="B", align=align, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", size=9)
    for item in items:
        values = [f"#{item['rank']}", item["material_id"], item["material_type"], item["packaging_type"],
                  f"{item['final_score']:.1f}", f"${item['predicted_cost_usd']:.2f}",
                  f"{item['predicted_co2_per_kg']:.3f}", f"{item['recyclability_percent']:.0f}%"]
        for (_, w, align), value in zip(columns, values):
            _fitted_cell(pdf, w * scale, 6.5, _latin1(value), align)
        pdf.ln()
        pdf.set_font("Helvetica", size=9)
    pdf.ln(5)

    _heading(pdf, "Final score (0-100)")
    label_w, bar_max = 30, width - 30 - 14
    for item in items:
        pdf.set_font("Helvetica", size=9)
        pdf.set_text_color(40, 40, 40)
        y = pdf.get_y()
        pdf.cell(label_w, 6, f"#{item['rank']} {item['material_id']}")
        pdf.set_fill_color(*GREEN)
        pdf.rect(pdf.l_margin + label_w, y + 1.2, bar_max * item["final_score"] / 100, 3.6, style="F")
        pdf.set_xy(pdf.l_margin + label_w + bar_max + 2, y)
        pdf.cell(12, 6, f"{item['final_score']:.1f}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(0, 4.5, _latin1(
        f"Predictions: cost by {report['models']['cost']}, CO2 by {report['models']['co2']}. Final score = weighted "
        f"CO2, cost, suitability and sustainability scores for the '{report['mode']}' mode "
        "(config/ranking_weights.yaml). Values come from the saved recommendation run and match the results page."))
    return pdf


def _fitted_cell(pdf: FPDF, width: float, height: float, text: str, align: str):
    """Shrink the font (down to 6 pt) so long names fit their column instead of overlapping the next one."""
    size = 9.0
    pdf.set_font("Helvetica", size=size)
    while pdf.get_string_width(text) > width - 2 and size > 6:
        size -= 0.5
        pdf.set_font("Helvetica", size=size)
    pdf.cell(width, height, text, border="B", align=align)


def _heading(pdf: FPDF, text: str):
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(200, 215, 207)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    pdf.set_text_color(40, 40, 40)          # body text after the green heading
