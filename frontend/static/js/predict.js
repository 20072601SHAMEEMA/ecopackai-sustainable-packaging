/*
 * EcoPackAI - Product Input Form: validation and submission
 * Module: Frontend UI
 *
 * 1. RULES / validateProduct() / buildPayload(): pure functions, no browser needed
 *    (unit-tested with Node: node --test tests/frontend/predict.test.js).
 * 2. Browser wiring: validates on submit (and per field after the first edit), shows
 *    errors next to each field plus a summary, and calls POST /recommend ONLY when
 *    every rule passes. The response is checked (EcoPackTable.validateRecommendResponse),
 *    shown as a sortable table under the form WITHOUT a page reload, and stored for
 *    results.html ("View charts & export").
 *
 * Allowed values must match the backend: categories = config/ranking_weights.yaml
 * (category_suitability), shipping types and fragility range = backend/routes/predict.py.
 * tests/test_frontend.py fails if they drift apart.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;                       // Node (unit tests)
  } else {
    root.EcoPackForm = api;                     // browser
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const RULES = {
    product_name: { required: true, minLength: 2, maxLength: 100 },
    category: {
      required: true,
      options: ["Food", "Drinkware", "Electronics", "Cosmetics", "Pharmacy", "Paper Product"],
    },
    product_weight_kg: { required: true, min: 0, minExclusive: true, max: 1000, maxDecimals: 3 },
    fragility_index: { required: true, integer: true, min: 1, max: 5 },
    shipping_type: { required: true, options: ["Air", "Road", "Sea"] },
    mode: { required: false, options: ["balanced", "sustainability_first", "cost_first"], default: "balanced" },
    top_n: { required: false, integer: true, min: 1, max: 20, default: 5 },
  };

  const LABELS = {
    product_name: "Product name",
    category: "Product category",
    product_weight_kg: "Weight (kg)",
    fragility_index: "Fragility index",
    shipping_type: "Shipping type",
    mode: "Ranking mode",
    top_n: "Number of recommendations",
  };

  function asText(value) {
    return value === undefined || value === null ? "" : String(value).trim();
  }

  /** Strict number parsing: "12", "0.5" and "1e3" are numbers; "12kg", "" and "0x1" are not. */
  function parseNumber(text) {
    if (!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(text)) return NaN;
    return Number(text);
  }

  function decimalsOf(text) {
    const match = /\.(\d+)$/.exec(text);
    return match ? match[1].length : 0;
  }

  /** Check one field; returns an error message or null. */
  function checkField(name, rawValue) {
    const rule = RULES[name];
    const label = LABELS[name];
    const text = asText(rawValue);

    if (text === "") {
      return rule.required ? `${label} is required.` : null;
    }
    if (rule.options) {
      return rule.options.includes(text) ? null : `${label} must be one of: ${rule.options.join(", ")}.`;
    }
    if (rule.minLength !== undefined) {
      if (text.length < rule.minLength) return `${label} must be at least ${rule.minLength} characters.`;
      if (text.length > rule.maxLength) return `${label} must be at most ${rule.maxLength} characters.`;
      return null;
    }
    const number = parseNumber(text);
    if (!Number.isFinite(number)) return `${label} must be a number.`;
    if (rule.integer && !Number.isInteger(number)) return `${label} must be a whole number.`;
    if (rule.minExclusive && number <= rule.min) return `${label} must be greater than ${rule.min}.`;
    if (!rule.minExclusive && number < rule.min) return `${label} must be at least ${rule.min}.`;
    if (number > rule.max) return `${label} must be at most ${rule.max}.`;
    if (rule.maxDecimals !== undefined && decimalsOf(text) > rule.maxDecimals) {
      return `${label} can have at most ${rule.maxDecimals} decimal places.`;
    }
    return null;
  }

  /** The request body for POST /recommend (only call with validated values). */
  function buildPayload(values) {
    const mode = asText(values.mode) || RULES.mode.default;
    const topN = asText(values.top_n) === "" ? RULES.top_n.default : parseNumber(asText(values.top_n));
    return {
      product: {
        product_name: asText(values.product_name),
        category: asText(values.category),
        product_weight_kg: parseNumber(asText(values.product_weight_kg)),
        fragility_index: parseNumber(asText(values.fragility_index)),
        shipping_type: asText(values.shipping_type),
      },
      options: { mode: mode, top_n: topN },
    };
  }

  /** Validate all fields; payload is null unless every rule passes. */
  function validateProduct(values) {
    const errors = {};
    Object.keys(RULES).forEach(function (name) {
      const message = checkField(name, values ? values[name] : undefined);
      if (message) errors[name] = message;
    });
    const valid = Object.keys(errors).length === 0;
    return { valid: valid, errors: errors, payload: valid ? buildPayload(values) : null };
  }

  return { RULES: RULES, LABELS: LABELS, checkField: checkField, validateProduct: validateProduct,
           buildPayload: buildPayload, parseNumber: parseNumber };
}));


/* ---------------------------------------------------------------------------
 * Browser wiring (skipped in Node)
 * ------------------------------------------------------------------------- */
(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const STORAGE = { result: "ecopackai:lastResult", product: "ecopackai:lastProduct",
                    apiBase: "ecopackai:apiBase", apiKey: "ecopackai:apiKey" };
  const TIMEOUT_MS = 15000;
  const Form = window.EcoPackForm;

  function storage() {
    try { return window.sessionStorage; } catch (e) { return null; }
  }

  function store(key, value) {
    const s = storage();
    if (!s) return;
    try { s.setItem(key, value); } catch (e) { /* storage full or blocked: not fatal */ }
  }

  function read(key) {
    const s = storage();
    if (!s) return null;
    try { return s.getItem(key); } catch (e) { return null; }
  }

  function defaultApiBase() {
    return window.location.protocol.startsWith("http") ? window.location.origin : "http://127.0.0.1:5000";
  }

  function init() {
    const form = document.getElementById("product-form");
    if (!form) return;
    const fields = Object.keys(Form.RULES);
    const touched = {};
    const summary = document.getElementById("form-errors");
    const status = document.getElementById("submit-status");
    const button = document.getElementById("submit-button");
    const apiBase = document.getElementById("api-base");
    const apiKey = document.getElementById("api-key");

    apiBase.value = read(STORAGE.apiBase) || defaultApiBase();
    apiKey.value = read(STORAGE.apiKey) || "";

    // "Edit and try again" from the results page: refill the last product
    if (new URLSearchParams(window.location.search).get("edit") === "1") {
      try {
        const last = JSON.parse(read(STORAGE.product) || "null");
        if (last) fields.forEach(function (name) { if (last[name] !== undefined) form.elements[name].value = last[name]; });
      } catch (e) { /* ignore a corrupted value */ }
    }

    function values() {
      const result = {};
      fields.forEach(function (name) { result[name] = form.elements[name].value; });
      return result;
    }

    function showFieldError(name, message) {
      const input = form.elements[name];
      const feedback = document.getElementById(name + "-error");
      input.classList.toggle("is-invalid", Boolean(message));
      input.setAttribute("aria-invalid", message ? "true" : "false");
      feedback.textContent = message || "";
    }

    function showSummary(errors) {
      const names = Object.keys(errors);
      summary.replaceChildren();
      if (!names.length) {
        summary.classList.add("d-none");
        return;
      }
      const title = document.createElement("strong");
      title.textContent = names.length === 1 ? "Please fix 1 problem:" : "Please fix " + names.length + " problems:";
      const list = document.createElement("ul");
      list.className = "mb-0 mt-1";
      names.forEach(function (name) {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = "#" + name;
        link.className = "alert-link";
        link.textContent = errors[name];
        link.addEventListener("click", function (event) { event.preventDefault(); form.elements[name].focus(); });
        item.appendChild(link);
        list.appendChild(item);
      });
      summary.append(title, list);
      summary.classList.remove("d-none");
    }

    function showStatus(kind, message) {
      status.className = "alert alert-" + kind + " mt-3";
      status.textContent = message;
    }

    function clearStatus() {
      status.className = "d-none";
      status.textContent = "";
    }

    // Per-field feedback once the user has interacted with a field
    fields.forEach(function (name) {
      const input = form.elements[name];
      const check = function () { if (touched[name]) showFieldError(name, Form.checkField(name, input.value)); };
      input.addEventListener("blur", function () { touched[name] = true; check(); });
      input.addEventListener("input", check);
      input.addEventListener("change", function () { touched[name] = true; check(); });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      clearStatus();
      const result = Form.validateProduct(values());
      fields.forEach(function (name) { touched[name] = true; showFieldError(name, result.errors[name]); });
      showSummary(result.errors);
      if (!result.valid) {
        form.elements[Object.keys(result.errors)[0]].focus();
        return;                                          // invalid: the API is never called
      }
      store(STORAGE.product, JSON.stringify(values()));
      store(STORAGE.apiBase, apiBase.value.trim());
      store(STORAGE.apiKey, apiKey.value.trim());
      submit(result.payload);
    });

    form.addEventListener("reset", function () {
      fields.forEach(function (name) { touched[name] = false; showFieldError(name, null); });
      showSummary({});
      clearStatus();
    });

    async function submit(payload) {
      const base = (apiBase.value.trim() || defaultApiBase()).replace(/\/+$/, "");
      const headers = { "Content-Type": "application/json" };
      if (apiKey.value.trim()) headers["X-API-Key"] = apiKey.value.trim();
      const controller = new AbortController();
      const timer = setTimeout(function () { controller.abort(); }, TIMEOUT_MS);

      button.disabled = true;
      button.querySelector(".spinner-border").classList.remove("d-none");
      showStatus("info", "Ranking materials for your product...");
      try {
        const response = await fetch(base + "/recommend", {
          method: "POST", headers: headers, body: JSON.stringify(payload), signal: controller.signal,
        });
        let body = null;
        try { body = await response.json(); } catch (e) { body = null; }

        if (response.ok && body && body.status === "success") {
          const check = window.EcoPackTable.validateRecommendResponse(body);
          if (!check.valid) {
            const reference = body.request_id ? " (request ID " + body.request_id + ")" : "";
            showStatus("danger", "The API answered, but the response was incomplete: " + check.problems[0] + reference);
            return;
          }
          store(STORAGE.result, JSON.stringify(body));
          showResults(body);
          return;
        }
        handleError(response.status, body);
      } catch (error) {
        showStatus("danger", error.name === "AbortError"
          ? "The API did not answer within 15 seconds. Please try again."
          : "Cannot reach the EcoPackAI API at " + base + ". Start it with 'python backend/app.py' " +
            "and open http://127.0.0.1:5000/ (or check the API address under API settings).");
      } finally {
        clearTimeout(timer);
        button.disabled = false;
        button.querySelector(".spinner-border").classList.add("d-none");
      }
    }

    const inline = {
      section: document.getElementById("inline-results"),
      summary: document.getElementById("inline-summary"),
      noResult: document.getElementById("inline-no-result"),
      card: document.getElementById("inline-table-card"),
      table: null,
    };

    /** Show the ranked materials under the form (no page reload). */
    function showResults(body) {
      const product = body.product || {};
      const count = body.recommendations.length;
      const modeName = { balanced: "Balanced", sustainability_first: "Sustainability first", cost_first: "Cost first" };
      inline.summary.textContent = (product.product_name || "Your product") + " · " + product.category +
        " · " + product.product_weight_kg + " kg · fragility " + product.fragility_index + " · " +
        product.shipping_type + " · " + (modeName[body.mode] || body.mode) + " mode · " +
        body.n_candidates + " materials passed the constraints";
      const empty = body.result === "no_valid_material" || count === 0;
      inline.noResult.classList.toggle("d-none", !empty);
      inline.card.classList.toggle("d-none", empty);
      if (!empty) {
        if (!inline.table) inline.table = window.EcoPackTable.createTable(document.getElementById("inline-table"));
        inline.table.render(body.recommendations);
      }
      inline.section.classList.remove("d-none");
      showStatus(empty ? "warning" : "success", empty
        ? "No material meets all constraints for this product."
        : "Ranked " + count + " materials — results are shown below the form.");
      const calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      inline.section.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "start" });
      inline.section.focus({ preventScroll: true });
    }

    function handleError(httpStatus, body) {
      const error = body && body.error ? body.error : {};
      const reference = body && body.request_id ? " (request ID " + body.request_id + ")" : "";
      if (httpStatus === 400 && error.code === "validation_error" && Array.isArray(error.details)) {
        const errors = {};
        error.details.forEach(function (detail) {
          const name = String(detail.field || "").replace(/^(product|options)\./, "");
          if (Form.RULES[name]) errors[name] = Form.LABELS[name] + ": " + detail.message;
        });
        Object.keys(errors).forEach(function (name) { showFieldError(name, errors[name]); });
        showSummary(errors);
        showStatus("danger", "The server rejected the request" + reference + ".");
      } else if (httpStatus === 401 || httpStatus === 403) {
        showStatus("warning", "The API needs a valid client key. Enter it under API settings" + reference + ".");
        document.getElementById("api-settings").open = true;
        apiKey.focus();
      } else {
        showStatus("danger", (error.message || "Unexpected response from the API (HTTP " + httpStatus + ")") + reference);
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}());
