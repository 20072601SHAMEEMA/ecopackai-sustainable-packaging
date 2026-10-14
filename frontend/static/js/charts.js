/*
 * EcoPackAI - Recommendation charts (Chart.js 4)
 * Module: Frontend Analytics
 *
 * Three charts on the results page, built only from the /recommend response:
 *   1. Predicted CO2 per kg for each recommended material      (bar)
 *   2. Predicted cost per unit for each recommended material   (bar)
 *   3. Final score ranking with the 4 criterion scores in the tooltip (horizontal bar)
 * Bars are coloured by packaging type; the legend lists the packaging types
 * (click a type to hide/show it). render() can be called again with a new
 * response: the existing charts are updated in place.
 *
 * chartData() is a pure function (unit-tested with Node: node --test tests/frontend/charts.test.js).
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.EcoPackCharts = api;
  }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // One fixed colour per packaging type, so a type has the same colour in every chart
  const PACKAGING_COLOURS = {
    "Cardboard Boxes": "#1f7a4d",
    "Protective Fillers (Paper/Biodegradable)": "#7fb069",
    "Bubble Wrap (Minimal Use)": "#e09f3e",
    "Foldable & Stackable Containers": "#3d6fb6",
    "Plastic Totes & Pallets": "#9b5de5",
    "Steel Racks & Containers": "#6c757d",
  };
  const FALLBACK_COLOUR = "#adb5bd";

  /** Turn a /recommend response into chart-ready arrays (same order as the results table). */
  function chartData(response) {
    const items = (response && response.recommendations) || [];
    const labels = items.map(function (item) { return "#" + item.rank + " " + item.material_id; });
    const types = [];
    items.forEach(function (item) { if (types.indexOf(item.packaging_type) === -1) types.push(item.packaging_type); });

    function series(field) {
      // one dataset per packaging type; null where a bar belongs to another type
      return types.map(function (type) {
        return {
          label: type,
          data: items.map(function (item) { return item.packaging_type === type ? item[field] : null; }),
          backgroundColor: PACKAGING_COLOURS[type] || FALLBACK_COLOUR,
        };
      });
    }

    return {
      labels: labels,
      packagingTypes: types,
      co2: series("predicted_co2_per_kg"),
      cost: series("predicted_cost_usd"),
      score: series("final_score"),
      scores: items.map(function (item) { return item.scores || {}; }),
      values: {
        co2: items.map(function (item) { return item.predicted_co2_per_kg; }),
        cost: items.map(function (item) { return item.predicted_cost_usd; }),
        score: items.map(function (item) { return item.final_score; }),
      },
    };
  }

  // ------------------------------------------------------------------ browser part
  const charts = {};

  function baseOptions(title, axisTitle, formatValue, horizontal) {
    const valueAxis = horizontal ? "x" : "y";
    const options = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      indexAxis: horizontal ? "y" : "x",
      datasets: { bar: { grouped: false, maxBarThickness: 48 } },     // one bar per material
      plugins: {
        title: { display: false, text: title },
        legend: { position: "bottom", labels: { boxWidth: 12, usePointStyle: true } },
        tooltip: {
          filter: function (item) { return item.raw !== null; },
          callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + formatValue(ctx.raw); } },
        },
      },
      scales: {},
    };
    options.scales[valueAxis] = { beginAtZero: true, title: { display: true, text: axisTitle } };
    return options;
  }

  function upsert(key, canvasId, data, datasets, options) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === "undefined") return null;
    if (charts[key]) {
      charts[key].data.labels = data.labels;
      charts[key].data.datasets = datasets;
      charts[key].options = options;
      charts[key].update();
    } else {
      charts[key] = new Chart(canvas, { type: "bar", data: { labels: data.labels, datasets: datasets }, options: options });
    }
    return charts[key];
  }

  /** Draw or update the three charts for a /recommend response. */
  function render(response) {
    const data = chartData(response);
    upsert("co2", "chart-co2", data, data.co2,
      baseOptions("Predicted CO2", "kg CO₂ per kg of material",
        function (v) { return v.toFixed(3) + " kg CO₂ per kg"; }, false));
    upsert("cost", "chart-cost", data, data.cost,
      baseOptions("Predicted cost", "USD per unit", function (v) { return "$" + v.toFixed(2) + " per unit"; }, false));

    const scoreOptions = baseOptions("Final score", "Final score (0–100)",
      function (v) { return v.toFixed(1) + " / 100"; }, true);
    scoreOptions.scales.x.max = 100;
    scoreOptions.plugins.tooltip.callbacks.afterLabel = function (ctx) {
      const s = data.scores[ctx.dataIndex] || {};
      const pct = function (v) { return typeof v === "number" ? Math.round(v * 100) + "%" : "–"; };
      return ["CO₂ score " + pct(s.co2), "Cost score " + pct(s.cost),
              "Suitability " + pct(s.suitability), "Sustainability " + pct(s.sustainability)];
    };
    upsert("score", "chart-score", data, data.score, scoreOptions);
    return data;
  }

  /** What each chart currently shows (used by the end-to-end tests). */
  function snapshot() {
    const out = {};
    Object.keys(charts).forEach(function (key) {
      const chart = charts[key];
      out[key] = {
        labels: chart.data.labels.slice(),
        legend: chart.data.datasets.map(function (d) { return d.label; }),
        values: chart.data.labels.map(function (_, i) {
          const hit = chart.data.datasets.find(function (d) { return d.data[i] !== null; });
          return hit ? hit.data[i] : null;
        }),
      };
    });
    return out;
  }

  return { chartData: chartData, render: render, snapshot: snapshot, PACKAGING_COLOURS: PACKAGING_COLOURS };
}));
