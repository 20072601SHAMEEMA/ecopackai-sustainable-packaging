/*
 * EcoPackAI - Unit tests for the chart data (frontend/static/js/charts.js)
 * Run with:  node --test tests/frontend/charts.test.js
 * Uses the real sample API response (frontend/static/js/sample_result.js).
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const Charts = require(path.join(__dirname, "..", "..", "frontend", "static", "js", "charts.js"));

function loadSample() {
  const sandbox = { window: {} };
  vm.runInNewContext(fs.readFileSync(
    path.join(__dirname, "..", "..", "frontend", "static", "js", "sample_result.js"), "utf8"), sandbox);
  return sandbox.window.ECOPACK_SAMPLE_RESULT;
}

const SAMPLE = loadSample();

test("labels follow the ranking order", () => {
  const data = Charts.chartData(SAMPLE);
  assert.deepEqual(data.labels, SAMPLE.recommendations.map((r) => "#" + r.rank + " " + r.material_id));
});

test("chart values are exactly the API values (no rounding)", () => {
  const data = Charts.chartData(SAMPLE);
  assert.deepEqual(data.values.co2, SAMPLE.recommendations.map((r) => r.predicted_co2_per_kg));
  assert.deepEqual(data.values.cost, SAMPLE.recommendations.map((r) => r.predicted_cost_usd));
  assert.deepEqual(data.values.score, SAMPLE.recommendations.map((r) => r.final_score));
});

test("one dataset per packaging type, each bar in exactly one dataset", () => {
  const data = Charts.chartData(SAMPLE);
  const types = [...new Set(SAMPLE.recommendations.map((r) => r.packaging_type))];
  for (const key of ["co2", "cost", "score"]) {
    assert.deepEqual(data[key].map((d) => d.label), types);
    SAMPLE.recommendations.forEach((rec, i) => {
      const filled = data[key].filter((d) => d.data[i] !== null);
      assert.equal(filled.length, 1);
      assert.equal(filled[0].label, rec.packaging_type);
    });
  }
});

test("a packaging type has the same colour in every chart", () => {
  const data = Charts.chartData(SAMPLE);
  for (let i = 0; i < data.co2.length; i++) {
    assert.equal(data.co2[i].backgroundColor, data.cost[i].backgroundColor);
    assert.equal(data.co2[i].backgroundColor, data.score[i].backgroundColor);
  }
  assert.equal(data.co2[0].backgroundColor, Charts.PACKAGING_COLOURS["Cardboard Boxes"]);
});

test("criterion scores are kept for the tooltip", () => {
  const data = Charts.chartData(SAMPLE);
  assert.deepEqual(data.scores[0], SAMPLE.recommendations[0].scores);
});

test("an empty or missing result gives empty charts, not an error", () => {
  for (const response of [null, {}, { recommendations: [] }]) {
    const data = Charts.chartData(response);
    assert.deepEqual(data.labels, []);
    assert.deepEqual(data.co2, []);
  }
});

test("unknown packaging types get the fallback colour", () => {
  const data = Charts.chartData({ recommendations: [{ rank: 1, material_id: "X", packaging_type: "New Type",
    predicted_co2_per_kg: 1, predicted_cost_usd: 2, final_score: 50 }] });
  assert.equal(data.co2[0].backgroundColor, "#adb5bd");
});
