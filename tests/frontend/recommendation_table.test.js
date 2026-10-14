/*
 * EcoPackAI - Unit tests for the response check and table sorting
 * (frontend/static/js/recommendation_table.js)
 * Run with:  node --test tests/frontend/recommendation_table.test.js
 * Uses the real sample API response (frontend/static/js/sample_result.js).
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const Table = require(path.join(__dirname, "..", "..", "frontend", "static", "js", "recommendation_table.js"));

function sample() {
  const sandbox = { window: {} };
  vm.runInNewContext(fs.readFileSync(
    path.join(__dirname, "..", "..", "frontend", "static", "js", "sample_result.js"), "utf8"), sandbox);
  return JSON.parse(JSON.stringify(sandbox.window.ECOPACK_SAMPLE_RESULT));     // fresh copy per test
}

// ---- validateRecommendResponse ----

test("the real API response is valid", () => {
  assert.deepEqual(Table.validateRecommendResponse(sample()), { valid: true, problems: [] });
});

test("a 'no valid material' response with an empty list is valid", () => {
  const body = Object.assign(sample(), { result: "no_valid_material", recommendations: [] });
  assert.equal(Table.validateRecommendResponse(body).valid, true);
});

test("non-objects and error responses are rejected", () => {
  for (const body of [null, "text", [], 42]) assert.equal(Table.validateRecommendResponse(body).valid, false);
  const error = { status: "error", error: { code: "internal_error" } };
  assert.equal(Table.validateRecommendResponse(error).valid, false);
});

test("missing or wrongly typed fields are reported by name", () => {
  const body = sample();
  delete body.recommendations[0].predicted_cost_usd;
  body.recommendations[1].final_score = "high";
  const result = Table.validateRecommendResponse(body);
  assert.equal(result.valid, false);
  assert.ok(result.problems.includes("recommendation 1: predicted_cost_usd is missing or invalid."));
  assert.ok(result.problems.includes("recommendation 2: final_score is missing or invalid."));
});

test("out-of-range values are rejected", () => {
  const body = sample();
  body.recommendations[0].final_score = 140;
  body.recommendations[1].predicted_co2_per_kg = -1;
  assert.equal(Table.validateRecommendResponse(body).problems.length, 2);
});

test("ranks must be 1, 2, 3, ... in order", () => {
  const body = sample();
  body.recommendations.reverse();
  assert.ok(Table.validateRecommendResponse(body).problems.includes("ranks must run 1, 2, 3, ... in order."));
});

test("result and list must agree", () => {
  assert.equal(Table.validateRecommendResponse(Object.assign(sample(), { recommendations: [] })).valid, false);
  assert.equal(Table.validateRecommendResponse(Object.assign(sample(), { result: "no_valid_material" })).valid, false);
});

test("a missing recommendations list is reported", () => {
  const body = sample();
  delete body.recommendations;
  assert.deepEqual(Table.validateRecommendResponse(body).problems, ["recommendations must be a list."]);
});

// ---- sortRecommendations ----

test("default order is by rank", () => {
  const items = sample().recommendations;
  assert.deepEqual(Table.sortRecommendations(items.slice().reverse(), "rank", "asc").map((r) => r.rank), [1, 2, 3, 4, 5]);
});

test("numeric columns sort both ways", () => {
  const items = sample().recommendations;
  for (const key of ["final_score", "predicted_cost_usd", "predicted_co2_per_kg", "recyclability_percent"]) {
    const up = Table.sortRecommendations(items, key, "asc").map((r) => r[key]);
    const down = Table.sortRecommendations(items, key, "desc").map((r) => r[key]);
    assert.deepEqual(up, up.slice().sort((a, b) => a - b), key);
    assert.deepEqual(down, down.slice().sort((a, b) => b - a), key);
  }
});

test("text columns sort alphabetically", () => {
  const items = sample().recommendations;
  const ids = Table.sortRecommendations(items, "material_id", "asc").map((r) => r.material_id);
  assert.deepEqual(ids, ids.slice().sort());
});

test("equal values keep rank order and the input is not changed", () => {
  const items = sample().recommendations;
  const before = JSON.stringify(items);
  const sorted = Table.sortRecommendations(items, "packaging_type", "asc");
  const cardboard = sorted.filter((r) => r.packaging_type === "Cardboard Boxes").map((r) => r.rank);
  assert.deepEqual(cardboard, cardboard.slice().sort((a, b) => a - b));
  assert.equal(JSON.stringify(items), before);
});

test("unknown sort keys are refused", () => {
  assert.throws(() => Table.sortRecommendations([], "price", "asc"), /Unknown sort key/);
});
