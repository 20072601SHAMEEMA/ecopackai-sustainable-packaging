"""
EcoPackAI - Wireframe Generator
Module: Frontend UI

Writes low-fidelity SVG wireframes (grey boxes on a 12-column Bootstrap grid)
for the four screens plus the user-flow diagram to docs/wireframes/.

Usage (from the project root):
    python scripts/make_wireframes.py
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "wireframes"
OUT.mkdir(parents=True, exist_ok=True)
W, MARGIN = 1200, 60
COL = (W - 2 * MARGIN) / 12          # Bootstrap-style 12-column grid


def x(col):
    return MARGIN + col * COL


def box(col, span, y, h, label="", fill="#f1f3f2", stroke="#9aa5a0", size=14, bold=False, dash=False):
    dash_attr = ' stroke-dasharray="6 4"' if dash else ""
    bold_attr = ' font-weight="bold"' if bold else ""
    parts = [f'<rect x="{x(col) + 6:.0f}" y="{y}" width="{span * COL - 12:.0f}" height="{h}" rx="6" '
             f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"{dash_attr}/>']
    if label:
        lines = label.split("\n")
        for i, line in enumerate(lines):
            ty = y + h / 2 + (i - (len(lines) - 1) / 2) * (size + 4) + size / 3
            parts.append(f'<text x="{x(col) + span * COL / 2:.0f}" y="{ty:.0f}" font-size="{size}" '
                         f'text-anchor="middle" fill="#3d4a44"{bold_attr}>{escape(line)}</text>')
    return "\n".join(parts)


def text(col, y, value, size=14, bold=False, anchor="start", fill="#3d4a44"):
    bold_attr = ' font-weight="bold"' if bold else ""
    return (f'<text x="{x(col) + 6:.0f}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{fill}"'
            f'{bold_attr}>{escape(value)}</text>')


def page(name, title, height, body, active):
    nav_items = ["Home", "Get Recommendation", "Results", "Analytics"]
    nav = [f'<rect x="0" y="0" width="{W}" height="56" fill="#cfd8d3"/>',
           text(0, 34, "EcoPackAI", 18, True)]
    nx = W - MARGIN
    for item in reversed(nav_items):
        width = len(item) * 8 + 20
        nx -= width
        weight = ' font-weight="bold" text-decoration="underline"' if item == active else ""
        nav.append(f'<text x="{nx + width / 2:.0f}" y="34" font-size="14" text-anchor="middle" fill="#3d4a44"{weight}>'
                   f'{escape(item)}</text>')
    footer_y = height - 50
    footer = [f'<rect x="0" y="{footer_y}" width="{W}" height="50" fill="#e3e8e5"/>',
              text(0, footer_y + 30, "Footer: project name  ·  model names", 13)]
    caption = text(0, height + 28, f"Wireframe — {title}  (low fidelity, 12-column Bootstrap grid, desktop)", 13,
                   fill="#6c7a72")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height + 40}" '
           f'viewBox="0 0 {W} {height + 40}" font-family="Segoe UI, Arial, sans-serif">\n'
           f'<rect width="{W}" height="{height + 40}" fill="#ffffff"/>\n'
           + "\n".join(nav + body + footer + [caption]) + "\n</svg>\n")
    (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")


# ---- Home ----
home = [
    box(0, 7, 90, 220, "Hero: headline + one-line pitch\n[ Get a recommendation ]", "#dfe7e2", size=16, bold=True),
    box(7, 2.5, 90, 105, "403\nmaterials"), box(9.5, 2.5, 90, 105, "6\ncategories"),
    box(7, 2.5, 205, 105, "0.998\ncost R²"), box(9.5, 2.5, 205, 105, "−53%\nCO₂ of top picks"),
    text(0, 360, "How it works", 18, True),
    box(0, 3, 380, 130, "1. Describe\nyour product"), box(3, 3, 380, 130, "2. Filter\nunsafe options"),
    box(6, 3, 380, 130, "3. Predict\ncost and CO₂"), box(9, 3, 380, 130, "4. Rank and\ncompare"),
    box(0, 6, 540, 130, "Card: Get a recommendation\n[ Open the product form ]"),
    box(6, 6, 540, 130, "Card: See an example\n[ View example results ]"),
]
page("01_home", "Home / Overview", 760, home, "Home")

# ---- Product input ----
form = [
    text(0, 105, "Describe your product", 22, True),
    box(0, 8, 120, 50, "Error summary (hidden until a submit fails)", "#fbe9e9", "#d9a3a3", 13, dash=True),
    box(0, 8, 185, 470, "", "#ffffff"),
    box(0.3, 7.4, 205, 50, "Product name *  [ text ]   hint: 2–100 chars"),
    box(0.3, 3.7, 270, 50, "Category *  [ select ▾ ]"), box(4, 3.7, 270, 50, "Weight (kg) *  [ number ]"),
    box(0.3, 3.7, 335, 50, "Fragility 1–5 *  [ select ▾ ]"), box(4, 3.7, 335, 50, "Shipping *  [ Air/Road/Sea ▾ ]"),
    box(0.3, 3.7, 410, 50, "Ranking mode  [ select ▾ ]"), box(4, 3.7, 410, 50, "Number of results  [ 1–20 ]"),
    box(0.3, 7.4, 475, 40, "▸ API settings (address, client key)", size=13),
    box(0.3, 2.2, 535, 46, "[ Get recommendations ]", "#cfd8d3", bold=True), box(2.5, 1.3, 535, 46, "[ Clear ]"),
    box(0.3, 7.4, 595, 40, "Status message (sending / API errors)", "#eef4fb", "#9fb7d1", 13, dash=True),
    box(8, 4, 185, 230, "Sidebar: What happens next\n1. checked in browser\n2. unsafe materials filtered\n"
                        "3. cost + CO₂ predicted\n4. results page", size=13),
    text(0, 690, "Under every field: red error text (hidden until invalid)  ·  * = required", 13, fill="#a94442"),
]
page("02_product_input", "Product input form", 760, form, "Get Recommendation")

# ---- Results ----
results = [
    text(0, 105, "Recommended packaging", 22, True),
    box(9, 1.5, 80, 40, "[ Edit ]", size=13), box(10.5, 1.5, 80, 40, "[ New ]", size=13),
    box(0, 12, 135, 45, "Notice: “Example data” (only when no live result)", "#e8f4fb", "#9fc6dc", 13, dash=True),
    box(0, 4, 200, 300, "Your product\ncategory · weight\nfragility · shipping\nmode · candidates", size=14),
    box(4, 8, 200, 90, "Best choice: material — packaging type\nscore · cost · CO₂ · recyclable",
        "#dfe7e2", bold=True),
    box(4, 8, 310, 50, "Rank | Material | Packaging | Score ███░ | Cost | CO₂ | Recyclable", "#e3e8e5", size=13),
] + [box(4, 8, 365 + i * 45, 40, f"#{i + 1}  row", "#ffffff", size=13) for i in range(5)] + [
    box(4, 8, 600, 50, "OR: “No suitable material found” + advice (when nothing passes)", "#fdf3e0", "#d9b66f", 13, dash=True),
    text(4, 680, "Model versions · request ID", 13, fill="#6c7a72"),
]
page("03_results", "Recommendation results", 760, results, "Results")

# ---- Dashboard ----
dash = [
    text(0, 105, "CO₂ & Cost Analytics", 22, True),
    box(8.5, 3.5, 80, 40, "Badge: placeholder", size=13),
] + [box(i * 3, 3, 140, 80, label) for i, label in enumerate(
    ["KPI: recommendations", "KPI: avg CO₂ of top picks", "KPI: avg cost of top picks", "KPI: cache hit rate"])] + [
    box(0, 6, 240, 200, "Chart: CO₂ by material type\n(bar)", dash=True),
    box(6, 6, 240, 200, "Chart: cost vs CO₂\n(scatter)", dash=True),
    box(0, 6, 455, 200, "Chart: most recommended\nmaterials (list)", dash=True),
    box(6, 6, 455, 200, "Chart: recommendations\nover time (line)", dash=True),
]
page("04_dashboard", "Analytics dashboard (placeholder)", 760, dash, "Analytics")

# ---- Flow ----
steps = [("Home", "index.html"), ("Product form", "predict.html"), ("validate in\nbrowser", "predict.js"),
         ("POST /recommend", "Flask API"), ("Results", "results.html")]
flow = []
bx = 30
for i, (label, sub) in enumerate(steps):
    fill = "#dfe7e2" if i in (0, 1, 4) else "#eef1f0"
    flow.append(f'<rect x="{bx}" y="60" width="190" height="90" rx="8" fill="{fill}" stroke="#7d8c85" stroke-width="1.5"/>')
    for j, line in enumerate(label.split("\n")):
        n_lines = len(label.split("\n"))
        flow.append(f'<text x="{bx + 95}" y="{97 + j * 18 - (n_lines - 1) * 9}" font-size="15" '
                    f'text-anchor="middle" font-weight="bold" fill="#2d3833">{escape(line)}</text>')
    flow.append(f'<text x="{bx + 95}" y="138" font-size="12" text-anchor="middle" fill="#5d6b64">{escape(sub)}</text>')
    if i < len(steps) - 1:
        flow.append(f'<line x1="{bx + 190}" y1="105" x2="{bx + 232}" y2="105" stroke="#3d4a44" stroke-width="2" '
                    f'marker-end="url(#arrow)"/>')
    bx += 235
flow += [
    '<path d="M 595 150 C 595 200, 385 200, 380 158" fill="none" stroke="#a94442" stroke-width="2" '
    'stroke-dasharray="6 4" marker-end="url(#arrow-red)"/>',
    '<text x="488" y="218" font-size="13" text-anchor="middle" fill="#a94442">invalid: errors shown, no API call</text>',
    '<path d="M 830 150 C 830 300, 345 300, 335 158" fill="none" stroke="#a94442" stroke-width="2" '
    'stroke-dasharray="6 4" marker-end="url(#arrow-red)"/>',
    '<text x="590" y="312" font-size="13" text-anchor="middle" fill="#a94442">API error (400 / 401 / unreachable): '
    'message on the form</text>',
    '<text x="30" y="360" font-size="13" fill="#5d6b64">results.html also opens directly: it shows a labelled sample '
    'when this tab has no result yet. dashboard.html is reachable from the navigation bar on every page.</text>',
]
svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1220" height="385" viewBox="0 0 1220 385" '
       'font-family="Segoe UI, Arial, sans-serif">\n<defs>'
       '<marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto">'
       '<path d="M0,0 L10,5 L0,10 z" fill="#3d4a44"/></marker>'
       '<marker id="arrow-red" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto">'
       '<path d="M0,0 L10,5 L0,10 z" fill="#a94442"/></marker></defs>\n'
       '<rect width="1220" height="385" fill="#ffffff"/>\n'
       '<text x="30" y="35" font-size="18" font-weight="bold" fill="#2d3833">EcoPackAI — user flow</text>\n'
       + "\n".join(flow) + "\n</svg>\n")
(OUT / "00_user_flow.svg").write_text(svg, encoding="utf-8")
print(sorted(p.name for p in OUT.iterdir()))
