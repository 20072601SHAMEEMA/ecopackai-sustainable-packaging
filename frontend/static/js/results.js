/*
 * EcoPackAI - Recommendation Results page
 * Module: Frontend UI & Analytics
 *
 * Shows the /recommend response saved by predict.js (sessionStorage): product
 * summary, best choice, ranked table and three charts (charts.js). If there is
 * no saved response (page opened directly, or no backend), it shows the bundled
 * sample from sample_result.js and says so.
 *
 * - Ranking-mode buttons call /recommend again for the same product; table and
 *   charts are re-rendered from the new response automatically.
 * - Export buttons download /reports/<run_id>.csv and .pdf (built by the API from
 *   the saved run, so the files match what is on screen).
 * - Every response is checked with EcoPackTable.validateRecommendResponse() before
 *   it is shown; the table is the shared sortable table (recommendation_table.js).
 *
 * All values are written with textContent, never as HTML.
 */
(function () {
  "use strict";

  const STORAGE = { result: "ecopackai:lastResult", product: "ecopackai:lastProduct",
                    apiBase: "ecopackai:apiBase", apiKey: "ecopackai:apiKey" };
  const MODE_LABELS = { balanced: "Balanced", sustainability_first: "Sustainability first", cost_first: "Cost first" };
  const TIMEOUT_MS = 15000;
  let current = null;          // the response currently on screen
  let isSample = false;
  let table = null;            // shared sortable table (recommendation_table.js)

  // ---------------------------------------------------------------- helpers
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function read(key) {
    try { return window.sessionStorage.getItem(key); } catch (e) { return null; }
  }

  function store(key, value) {
    try { window.sessionStorage.setItem(key, value); } catch (e) { /* not fatal */ }
  }

  function apiBase() {
    const saved = read(STORAGE.apiBase);
    const fallback = window.location.protocol.startsWith("http") ? window.location.origin : "http://127.0.0.1:5000";
    return (saved || fallback).replace(/\/+$/, "");
  }

  function apiHeaders() {
    const key = read(STORAGE.apiKey);
    return key ? { "X-API-Key": key } : {};
  }

  function fmt(value, digits) {
    return typeof value === "number" ? value.toFixed(digits) : "–";
  }

  function showStatus(kind, message) {
    const status = document.getElementById("action-status");
    status.className = "alert alert-" + kind + " py-2 mt-3 mb-0";
    status.textContent = message;
  }

  function clearStatus() {
    const status = document.getElementById("action-status");
    status.className = "d-none";
    status.textContent = "";
  }

  async function fetchWithTimeout(url, options) {
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, TIMEOUT_MS);
    try {
      return await fetch(url, Object.assign({ signal: controller.signal }, options));
    } finally {
      clearTimeout(timer);
    }
  }

  function describeFailure(error, httpStatus, body) {
    if (error) {
      return error.name === "AbortError" ? "The API did not answer within 15 seconds."
        : "Cannot reach the EcoPackAI API at " + apiBase() + ". Start it with 'python backend/app.py'.";
    }
    if (httpStatus === 401 || httpStatus === 403) return "The API needs a valid client key (enter it on the product form under API settings).";
    const reference = body && body.request_id ? " (request ID " + body.request_id + ")" : "";
    return ((body && body.error && body.error.message) || "Unexpected response from the API (HTTP " + httpStatus + ")") + reference;
  }

  // ---------------------------------------------------------------- rendering
  function renderProduct(data) {
    const product = data.product || {};
    const list = document.getElementById("product-summary");
    const rows = [
      ["Product", product.product_name || "(unnamed)"],
      ["Category", product.category],
      ["Weight", fmt(product.product_weight_kg, 2) + " kg"],
      ["Fragility", product.fragility_index + " / 5"],
      ["Shipping", product.shipping_type],
      ["Ranking mode", MODE_LABELS[data.mode] || data.mode],
      ["Materials that passed the constraints", data.n_candidates],
    ];
    list.replaceChildren();
    rows.forEach(function (row) {
      list.append(el("dt", "col-sm-6 col-lg-12 col-xl-6", row[0]), el("dd", "col-sm-6 col-lg-12 col-xl-6", row[1]));
    });
  }

  function renderTable(data) {
    if (!table) table = window.EcoPackTable.createTable(document.getElementById("results-table"));
    table.render(data.recommendations);
  }

  function renderBest(data) {
    const best = data.recommendations[0];
    document.getElementById("best-material").textContent = best.material_id + " — " + best.packaging_type;
    document.getElementById("best-details").textContent =
      "Score " + fmt(best.final_score, 1) + " / 100 · $" + fmt(best.predicted_cost_usd, 2) +
      " per unit · " + fmt(best.predicted_co2_per_kg, 3) + " kg CO₂ per kg · " +
      fmt(best.recyclability_percent, 0) + "% recyclable";
  }

  function renderModeButtons(mode) {
    document.querySelectorAll("#mode-switch [data-mode]").forEach(function (button) {
      const active = button.getAttribute("data-mode") === mode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function renderExportButtons(data) {
    const enabled = !isSample && Boolean(data.run_id);
    ["export-csv", "export-pdf"].forEach(function (id) {
      const button = document.getElementById(id);
      button.disabled = !enabled;
      button.title = enabled ? "" : "Make your own recommendation first: exports are built from a saved run.";
    });
  }

  /** Draw everything for one /recommend response. Safe to call again with a new response. */
  function render(data) {
    current = data;
    renderProduct(data);
    renderModeButtons(data.mode);
    renderExportButtons(data);

    const model = data.model || {};
    document.getElementById("model-info").textContent = model.cost && model.co2
      ? "Cost: " + model.cost.name + " v" + model.cost.version + " · CO₂: " + model.co2.name + " v" + model.co2.version : "";
    document.getElementById("request-id").textContent = data.request_id ? "Request ID: " + data.request_id : "";

    const warnings = document.getElementById("warnings");
    warnings.replaceChildren();
    const empty = data.result === "no_valid_material" || !data.recommendations || !data.recommendations.length;
    document.getElementById("no-result").classList.toggle("d-none", !empty);
    document.getElementById("results-section").classList.toggle("d-none", empty);
    if (empty) return;

    renderBest(data);
    renderTable(data);
    if (window.EcoPackCharts && typeof Chart !== "undefined") {
      window.EcoPackCharts.render(data);
    } else {
      document.getElementById("charts").replaceChildren(
        el("div", "col-12 small text-body-secondary", "The chart library (static/vendor/chart-4.4.4.umd.js) could not be loaded."));
    }
    (data.warnings || []).forEach(function (warning) {
      warnings.appendChild(el("div", "alert alert-warning py-2 mb-2", warning));
    });
  }

  // ---------------------------------------------------------------- actions
  async function changeMode(mode) {
    if (!current || mode === current.mode) return;
    const spinner = document.getElementById("mode-spinner");
    const buttons = document.querySelectorAll("#mode-switch [data-mode]");
    buttons.forEach(function (b) { b.disabled = true; });
    spinner.classList.remove("d-none");
    clearStatus();
    const product = Object.assign({}, current.product);
    delete product.product_id;                   // re-rank the same attributes as an inline product
    try {
      let response;
      try {
        response = await fetchWithTimeout(apiBase() + "/recommend", {
          method: "POST",
          headers: Object.assign({ "Content-Type": "application/json" }, apiHeaders()),
          body: JSON.stringify({ product: product, options: { mode: mode, top_n: current.top_n } }),
        });
      } catch (error) {
        showStatus("danger", describeFailure(error));
        return;
      }
      let body = null;
      try { body = await response.json(); } catch (e) { body = null; }
      if (!response.ok || !body || body.status !== "success") {
        showStatus("danger", describeFailure(null, response.status, body));
        return;
      }
      const check = window.EcoPackTable.validateRecommendResponse(body);
      if (!check.valid) {
        showStatus("danger", "The API answered, but the response was incomplete (" + check.problems[0] +
                   "). The previous results are still shown.");
        return;
      }
      isSample = false;
      document.getElementById("sample-notice").classList.add("d-none");
      store(STORAGE.result, JSON.stringify(body));
      render(body);
      showStatus("success", "Updated: ranked with “" + MODE_LABELS[mode] + "”.");
    } finally {
      buttons.forEach(function (b) { b.disabled = false; });
      spinner.classList.add("d-none");
    }
  }

  async function exportFile(kind) {
    if (!current || !current.run_id) return;
    const button = document.getElementById(kind === "csv" ? "export-csv" : "export-pdf");
    button.disabled = true;
    clearStatus();
    try {
      let response;
      try {
        response = await fetchWithTimeout(apiBase() + "/reports/" + current.run_id + "." + kind, { headers: apiHeaders() });
      } catch (error) {
        showStatus("danger", describeFailure(error));
        return;
      }
      if (!response.ok) {
        let body = null;
        try { body = await response.json(); } catch (e) { body = null; }
        showStatus("danger", describeFailure(null, response.status, body));
        return;
      }
      const disposition = response.headers.get("Content-Disposition") || "";
      const match = /filename="([^"]+)"/.exec(disposition);
      const name = match ? match[1] : "ecopackai_run" + current.run_id + "." + kind;
      const url = URL.createObjectURL(await response.blob());
      const link = el("a");
      link.href = url;
      link.download = name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
      showStatus("success", "Downloaded " + name);
    } finally {
      button.disabled = false;
    }
  }

  // ---------------------------------------------------------------- start
  function init() {
    let saved = null;
    try { saved = JSON.parse(read(STORAGE.result) || "null"); } catch (e) { saved = null; }
    if (saved && !window.EcoPackTable.validateRecommendResponse(saved).valid) saved = null;   // damaged: use the sample
    const data = saved || window.ECOPACK_SAMPLE_RESULT;
    isSample = data !== saved;
    if (isSample) document.getElementById("sample-notice").classList.remove("d-none");
    if (!data) return;

    document.querySelectorAll("#mode-switch [data-mode]").forEach(function (button) {
      button.addEventListener("click", function () { changeMode(button.getAttribute("data-mode")); });
    });
    document.getElementById("export-csv").addEventListener("click", function () { exportFile("csv"); });
    document.getElementById("export-pdf").addEventListener("click", function () { exportFile("pdf"); });
    render(data);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}());
