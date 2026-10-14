/*
 * EcoPackAI - Sample /recommend response (real API output, Chocolate Box, balanced mode).
 * Shown by results.html when no live result is stored, so the page works without the backend.
 * request_id, run_id and processing_ms are cleared because they belong to one specific call.
 */
window.ECOPACK_SAMPLE_RESULT = {
  "cached": false,
  "mode": "balanced",
  "model": {
    "co2": {
      "name": "XGBRegressor",
      "target": "co2_emission_per_kg",
      "unit": "kg CO2 per kg of material",
      "version": 1
    },
    "cost": {
      "name": "RandomForestRegressor",
      "target": "cost_per_unit_usd",
      "unit": "USD per unit",
      "version": 1
    },
    "package_version": "1.0.0"
  },
  "n_candidates": 153,
  "processing_ms": null,
  "product": {
    "category": "Food",
    "fragility_index": 2,
    "product_name": "Chocolate Box",
    "product_weight_kg": 0.5,
    "shipping_type": "Air"
  },
  "recommendations": [
    {
      "final_score": 81.5715,
      "material_id": "MAT_0154",
      "material_type": "Cardboard",
      "packaging_type": "Cardboard Boxes",
      "predicted_co2_per_kg": 0.5102,
      "predicted_cost_usd": 2.7885,
      "rank": 1,
      "recyclability_percent": 100.0,
      "scores": {
        "co2": 0.9286,
        "cost": 0.9136,
        "suitability": 0.5333,
        "sustainability": 0.8649
      }
    },
    {
      "final_score": 80.5389,
      "material_id": "MAT_0237",
      "material_type": "Cardboard",
      "packaging_type": "Cardboard Boxes",
      "predicted_co2_per_kg": 0.509,
      "predicted_cost_usd": 2.8263,
      "rank": 2,
      "recyclability_percent": 98.0,
      "scores": {
        "co2": 0.929,
        "cost": 0.9121,
        "suitability": 0.5067,
        "sustainability": 0.8426
      }
    },
    {
      "final_score": 80.1011,
      "material_id": "MAT_0178",
      "material_type": "Cardboard",
      "packaging_type": "Cardboard Boxes",
      "predicted_co2_per_kg": 0.507,
      "predicted_cost_usd": 3.129,
      "rank": 3,
      "recyclability_percent": 95.0,
      "scores": {
        "co2": 0.9297,
        "cost": 0.8999,
        "suitability": 0.5067,
        "sustainability": 0.8363
      }
    },
    {
      "final_score": 74.0937,
      "material_id": "MAT_0051",
      "material_type": "Plastic",
      "packaging_type": "Bubble Wrap (Minimal Use)",
      "predicted_co2_per_kg": 1.4764,
      "predicted_cost_usd": 1.2369,
      "rank": 4,
      "recyclability_percent": 78.0,
      "scores": {
        "co2": 0.5887,
        "cost": 0.9759,
        "suitability": 0.86,
        "sustainability": 0.3772
      }
    },
    {
      "final_score": 73.558,
      "material_id": "MAT_0075",
      "material_type": "Plastic",
      "packaging_type": "Bubble Wrap (Minimal Use)",
      "predicted_co2_per_kg": 1.5488,
      "predicted_cost_usd": 1.0958,
      "rank": 5,
      "recyclability_percent": 82.0,
      "scores": {
        "co2": 0.5632,
        "cost": 0.9815,
        "suitability": 0.86,
        "sustainability": 0.3811
      }
    }
  ],
  "request_id": null,
  "result": "ok",
  "run_id": null,
  "status": "success",
  "top_n": 5,
  "warnings": []
};
