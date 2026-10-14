/*
 * EcoPackAI - Recommendation table and response contract
 * Module: Frontend UI <-> Backend integration
 *
 * Shared by predict.html (results shown under the form, no page reload) and
 * results.html (full analysis).
 *
 * Pure functions (unit-tested with Node: node --test tests/frontend/recommendation_table.test.js):
 *   validateRecommendResponse(body) -> {valid, problems}   checks a /recommend response before it is shown
 *   sortRecommendations(items, key, direction)              sorted copy; ties keep rank order
 * Browser:
 *   createTable(tableElement) -> {render(items), sortBy(key, direction), state()}
 *     Sortable column headers (th[data-sort]); rank 1 is highlighted as the top pick.
 *
 * All values are written with textContent, never as HTML.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.EcoPackTable = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // field -> [type, minimum, maximum] for every recommended material
  const ITEM_FIELDS = {
    rank: ["integer", 1, Infinity],
    material_id: ["string"],
    material_type: ["string"],
    packaging_type: ["string"],
    final_score: ["number", 0, 100],
    predicted_cost_usd: ["number", 0, Infinity],
    predicted_co2_per_kg: ["number", 0, Infinity],
    recyclability_percent: ["number", 0, 100],
  };

  // sortable columns: key -> direction used on the first click
  const SORT_KEYS = {
    rank: "asc",
    material_id: "asc",
    packaging_type: "asc",
    final_score: "desc",
    predicted_cost_usd: "asc",
    predicted_co2_per_kg: "asc",
    recyclability_percent: "desc",
  };

  function typeOk(value, spec) {
    const kind = spec[0];
    if (kind === "string") return typeof value === "string" && value.length > 0;
    if (typeof value !== "number" || !Number.isFinite(value)) return false;
    if (kind === "integer" && !Number.isInteger(value)) return false;
    return value >= spec[1] && value <= spec[2];
  }

  /** Check that a /recommend response has everything the page needs, before showing it. */
  function validateRecommendResponse(body) {
    const problems = [];
    if (!body || typeof body !== "object" || Array.isArray(body)) {
      return { valid: false, problems: ["The response is not a JSON object."] };
    }
    if (body.status !== "success") problems.push("status is not \"success\".");
    if (!body.product || typeof body.product !== "object") problems.push("product details are missing.");
    if (typeof body.mode !== "string") problems.push("ranking mode is missing.");
    if (["ok", "no_valid_material"].indexOf(body.result) === -1) problems.push("result must be \"ok\" or \"no_valid_material\".");
    if (!Array.isArray(body.recommendations)) {
      problems.push("recommendations must be a list.");
      return { valid: false, problems: problems };
    }
    if (body.result === "ok" && body.recommendations.length === 0) problems.push("result is \"ok\" but the list is empty.");
    if (body.result === "no_valid_material" && body.recommendations.length > 0) {
      problems.push("result is \"no_valid_material\" but materials were listed.");
    }
    body.recommendations.forEach(function (item, i) {
      if (!item || typeof item !== "object") {
        problems.push("recommendation " + (i + 1) + " is not an object.");
        return;
      }
      Object.keys(ITEM_FIELDS).forEach(function (field) {
        if (!typeOk(item[field], ITEM_FIELDS[field])) {
          problems.push("recommendation " + (i + 1) + ": " + field + " is missing or invalid.");
        }
      });
      if (item.rank !== i + 1) problems.push("ranks must run 1, 2, 3, ... in order.");
    });
    return { valid: problems.length === 0, problems: problems.filter(function (p, i, all) { return all.indexOf(p) === i; }) };
  }

  /** Sorted copy of the recommendations; equal values keep their rank order. */
  function sortRecommendations(items, key, direction) {
    if (!SORT_KEYS[key]) throw new Error("Unknown sort key: " + key);
    const factor = direction === "desc" ? -1 : 1;
    return items.slice().sort(function (a, b) {
      const x = a[key];
      const y = b[key];
      const order = typeof x === "string" ? x.localeCompare(y) : x - y;
      return order !== 0 ? order * factor : a.rank - b.rank;
    });
  }

  // ------------------------------------------------------------------ browser part
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function fmt(value, digits) {
    return typeof value === "number" ? value.toFixed(digits) : "–";
  }

  function scoreBar(score) {
    const wrapper = el("div", "d-flex align-items-center gap-2");
    const bar = el("div", "progress flex-grow-1 score-bar");
    bar.setAttribute("role", "progressbar");
    bar.setAttribute("aria-label", "Final score");
    bar.setAttribute("aria-valuenow", fmt(score, 1));
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", "100");
    const fill = el("div", "progress-bar bg-eco");
    fill.style.width = Math.max(0, Math.min(100, score)) + "%";
    bar.appendChild(fill);
    wrapper.append(bar, el("span", "fw-semibold score-value", fmt(score, 1)));
    return wrapper;
  }

  function row(item) {
    const tr = el("tr");
    tr.setAttribute("data-rank", String(item.rank));
    if (item.rank === 1) tr.className = "top-pick";
    const material = el("td");
    material.append(el("div", "fw-semibold", item.material_id), el("div", "small text-body-secondary", item.material_type));
    if (item.rank === 1) material.appendChild(el("span", "badge text-bg-success mt-1", "Top pick"));
    const score = el("td");
    score.appendChild(scoreBar(item.final_score));
    tr.append(el("td", "fw-bold", "#" + item.rank), material, el("td", null, item.packaging_type), score,
              el("td", "text-end", "$" + fmt(item.predicted_cost_usd, 2)),
              el("td", "text-end", fmt(item.predicted_co2_per_kg, 3)),
              el("td", "text-end", fmt(item.recyclability_percent, 0) + "%"));
    return tr;
  }

  /** Turn a <table> with th[data-sort] headers into a sortable recommendation table. */
  function createTable(table) {
    const body = table.querySelector("tbody");
    const headers = Array.prototype.slice.call(table.querySelectorAll("th[data-sort]"));
    let items = [];
    let key = "rank";
    let direction = "asc";

    headers.forEach(function (th) {
      const button = el("button", "sort-btn", th.textContent.trim());
      button.type = "button";
      button.appendChild(el("span", "sort-icon ms-1", ""));
      button.addEventListener("click", function () {
        const column = th.getAttribute("data-sort");
        const next = column === key ? (direction === "asc" ? "desc" : "asc") : SORT_KEYS[column];
        sortBy(column, next);
      });
      th.replaceChildren(button);
    });

    function updateHeaders() {
      headers.forEach(function (th) {
        const active = th.getAttribute("data-sort") === key;
        th.setAttribute("aria-sort", active ? (direction === "asc" ? "ascending" : "descending") : "none");
        th.querySelector(".sort-icon").textContent = active ? (direction === "asc" ? "▲" : "▼") : "⇅";
      });
    }

    function draw() {
      body.replaceChildren();
      sortRecommendations(items, key, direction).forEach(function (item) { body.appendChild(row(item)); });
      updateHeaders();
    }

    function sortBy(column, dir) {
      key = column;
      direction = dir || SORT_KEYS[column];
      draw();
    }

    return {
      render: function (list) { items = list.slice(); draw(); },
      sortBy: sortBy,
      state: function () { return { key: key, direction: direction }; },
    };
  }

  return { validateRecommendResponse: validateRecommendResponse, sortRecommendations: sortRecommendations,
           createTable: createTable, ITEM_FIELDS: ITEM_FIELDS, SORT_KEYS: SORT_KEYS, fmt: fmt };
}));
