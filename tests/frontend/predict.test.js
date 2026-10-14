/*
 * EcoPackAI - Unit tests for the product form validation (frontend/static/js/predict.js)
 * Run with:  node --test tests/frontend/predict.test.js
 * (also run from pytest by tests/test_frontend.py)
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const Form = require(path.join(__dirname, "..", "..", "frontend", "static", "js", "predict.js"));

const VALID = {
  product_name: "Chocolate Box",
  category: "Food",
  product_weight_kg: "0.5",
  fragility_index: "2",
  shipping_type: "Air",
  mode: "balanced",
  top_n: "5",
};

function withChange(field, value) {
  return Object.assign({}, VALID, { [field]: value });
}

function errorFor(field, value) {
  return Form.validateProduct(withChange(field, value)).errors[field];
}

test("a complete, valid form passes and builds the API payload", () => {
  const result = Form.validateProduct(VALID);
  assert.equal(result.valid, true);
  assert.deepEqual(result.errors, {});
  assert.deepEqual(result.payload, {
    product: { product_name: "Chocolate Box", category: "Food", product_weight_kg: 0.5,
               fragility_index: 2, shipping_type: "Air" },
    options: { mode: "balanced", top_n: 5 },
  });
});

test("numbers in the payload are real numbers, not strings", () => {
  const { payload } = Form.validateProduct(VALID);
  assert.equal(typeof payload.product.product_weight_kg, "number");
  assert.equal(typeof payload.product.fragility_index, "number");
  assert.equal(typeof payload.options.top_n, "number");
});

test("an empty form reports every required field and builds no payload", () => {
  const result = Form.validateProduct({});
  assert.equal(result.valid, false);
  assert.equal(result.payload, null);
  assert.deepEqual(Object.keys(result.errors).sort(),
    ["category", "fragility_index", "product_name", "product_weight_kg", "shipping_type"]);
});

test("whitespace-only values count as empty", () => {
  assert.match(errorFor("product_name", "   "), /required/);
});

test("product name length limits", () => {
  assert.match(errorFor("product_name", "A"), /at least 2/);
  assert.equal(errorFor("product_name", "AB"), undefined);
  assert.equal(errorFor("product_name", "x".repeat(100)), undefined);
  assert.match(errorFor("product_name", "x".repeat(101)), /at most 100/);
});

test("product name is trimmed in the payload", () => {
  assert.equal(Form.validateProduct(withChange("product_name", "  Box  ")).payload.product.product_name, "Box");
});

test("category must be one of the six backend categories (case-sensitive)", () => {
  for (const category of ["Food", "Drinkware", "Electronics", "Cosmetics", "Pharmacy", "Paper Product"]) {
    assert.equal(errorFor("category", category), undefined, category);
  }
  assert.match(errorFor("category", "Toys"), /must be one of/);
  assert.match(errorFor("category", "food"), /must be one of/);
});

test("weight must be a number greater than 0 and at most 1000", () => {
  assert.match(errorFor("product_weight_kg", "0"), /greater than 0/);
  assert.match(errorFor("product_weight_kg", "-2"), /greater than 0/);
  assert.equal(errorFor("product_weight_kg", "0.001"), undefined);
  assert.equal(errorFor("product_weight_kg", "1000"), undefined);
  assert.match(errorFor("product_weight_kg", "1000.5"), /at most 1000/);
});

test("weight rejects text, units and odd number formats", () => {
  for (const bad of ["abc", "12kg", "1,5", "0x10", "Infinity", "NaN", "--1", "1.2.3"]) {
    assert.match(errorFor("product_weight_kg", bad), /must be a number/, bad);
  }
});

test("weight allows at most 3 decimals", () => {
  assert.equal(errorFor("product_weight_kg", "1.234"), undefined);
  assert.match(errorFor("product_weight_kg", "1.2345"), /3 decimal/);
});

test("fragility index must be a whole number from 1 to 5", () => {
  for (const ok of ["1", "3", "5"]) assert.equal(errorFor("fragility_index", ok), undefined, ok);
  assert.match(errorFor("fragility_index", "0"), /at least 1/);
  assert.match(errorFor("fragility_index", "6"), /at most 5/);
  assert.match(errorFor("fragility_index", "2.5"), /whole number/);
});

test("shipping type must be Air, Road or Sea", () => {
  for (const ok of ["Air", "Road", "Sea"]) assert.equal(errorFor("shipping_type", ok), undefined, ok);
  assert.match(errorFor("shipping_type", "Rail"), /must be one of/);
});

test("mode and top_n are optional with defaults", () => {
  const result = Form.validateProduct(Object.assign({}, VALID, { mode: "", top_n: "" }));
  assert.equal(result.valid, true);
  assert.deepEqual(result.payload.options, { mode: "balanced", top_n: 5 });
});

test("mode must be a known ranking mode", () => {
  assert.equal(errorFor("mode", "cost_first"), undefined);
  assert.match(errorFor("mode", "fastest"), /must be one of/);
});

test("top_n must be a whole number from 1 to 20", () => {
  assert.equal(errorFor("top_n", "20"), undefined);
  assert.match(errorFor("top_n", "0"), /at least 1/);
  assert.match(errorFor("top_n", "21"), /at most 20/);
  assert.match(errorFor("top_n", "3.5"), /whole number/);
});

test("all errors are reported together", () => {
  const result = Form.validateProduct({ product_name: "A", category: "Toys", product_weight_kg: "-1",
                                        fragility_index: "9", shipping_type: "Rail", top_n: "50" });
  assert.equal(Object.keys(result.errors).length, 6);
});

test("error messages name the field", () => {
  assert.match(errorFor("product_weight_kg", ""), /^Weight \(kg\)/);
  assert.match(errorFor("fragility_index", ""), /^Fragility index/);
});
