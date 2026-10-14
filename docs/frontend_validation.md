# Product Form — Validation Rules and Behaviour

**Code:** `frontend/static/js/predict.js` · **Form:** `frontend/predict.html` ·
**Tests:** `tests/frontend/predict.test.js` (17 Node tests), `tests/test_frontend.py`

## 1. Fields and Rules

| Field (`name`) | Control | Required | Rule | Example error |
|---|---|---|---|---|
| `product_name` | text | yes | 2–100 characters after trimming spaces | "Product name must be at least 2 characters." |
| `category` | select | yes | Food, Drinkware, Electronics, Cosmetics, Pharmacy or Paper Product (exact) | "Product category is required." |
| `product_weight_kg` | text (decimal keypad) | yes | Number > 0 and ≤ 1000, at most 3 decimals | "Weight (kg) must be greater than 0." |
| `fragility_index` | select | yes | Whole number 1–5 | "Fragility index must be at most 5." |
| `shipping_type` | select | yes | Air, Road or Sea | "Shipping type must be one of: Air, Road, Sea." |
| `mode` | select | no (default `balanced`) | balanced, sustainability_first or cost_first | "Ranking mode must be one of: …" |
| `top_n` | text (number keypad) | no (default 5) | Whole number 1–20 | "Number of recommendations must be at most 20." |

**Numbers are parsed strictly.** `0.5`, `12` and `1e3` are numbers; `12kg`, `1,5`, `0x10`,
`Infinity` and empty text are not. (JavaScript's own `parseFloat("12kg")` would quietly
give 12, so it is not used.)

**Why these limits**
- Allowed values are exactly what the API accepts (checked by `tests/test_frontend.py`
  against the backend config), so a valid form is never rejected by the server for its values.
- Weight ≤ 1000 kg and 3 decimals are frontend-only sanity limits that catch typos (the
  catalogue's heaviest product is 15 kg); the API itself only requires > 0.
- Name ≤ 100 characters matches the `products.product_name` database column.
- Select boxes limit what can be chosen, but the values are still validated, because a page
  can be modified in the browser.

## 2. Behaviour

| When | What the user sees |
|---|---|
| Typing in a field never touched before | Nothing yet (no errors while filling in for the first time) |
| Leaving a field, or changing a select | That field is checked; error shown or cleared |
| Typing in a field already checked | The error updates live and disappears as soon as the value is valid |
| Submitting with problems | Every invalid field turns red with its message; a summary at the top lists all problems as links to the fields; the cursor moves to the first problem; **no request is sent** |
| Submitting a valid form | Button disabled with a spinner, "Ranking materials…" message; one `POST /recommend` |
| API success | Response checked, then the ranked table appears under the form (no page reload) with "View charts & export" |
| API 400 (server validation) | Server messages shown on the matching fields and in the summary |
| API 401 / 403 | "The API needs a valid client key…"; API settings open, cursor in the key field |
| API not reachable | "Cannot reach the EcoPackAI API at … Start it with 'python backend/app.py'…" |
| No answer in 15 s | "The API did not answer within 15 seconds. Please try again." |
| "Clear" | Form, errors and messages are reset |
| "Edit product" (results page) | Form opens with the previous values filled in |

All messages name the field ("Weight (kg) must be a number.") and say how to fix it.

## 3. Request Payload

Built by `buildPayload()` only after every rule passes; numbers are sent as JSON numbers:

```json
{
  "product": {
    "product_name": "Chocolate Box",
    "category": "Food",
    "product_weight_kg": 0.5,
    "fragility_index": 2,
    "shipping_type": "Air"
  },
  "options": {"mode": "balanced", "top_n": 5}
}
```

Sent as `POST <API address>/recommend` with `Content-Type: application/json` and, if a key
is entered under API settings, `X-API-Key: <key>`. The API address defaults to the page's own
address when served by Flask, or `http://127.0.0.1:5000` when the page is opened as a file.

## 4. How It Was Verified

**Automated**
- 17 Node unit tests: valid form and exact payload; numbers typed correctly; empty form;
  whitespace-only text; every limit on both sides; rejected number formats; decimals;
  optional fields and defaults; all errors reported together; messages name the field.
- `tests/test_frontend.py`: the Node tests pass; allowed values match the backend; every
  field has a label, error slot and `aria-describedby`; select options match the rules; a
  payload built by `predict.js` is accepted by the real `/recommend` endpoint.

**In a real browser** (Flask server, API key required):

| Test | Result |
|---|---|
| Submit the empty form | 5 errors, focus on "Product name", **0 requests** to `/recommend` |
| Name "A", weight "12kg", 50 results | Exactly those 3 fields flagged with specific messages, **0 requests** |
| Correct the weight | Its error disappears while typing |
| Valid form, no API key | 1 request → 401 → key message, API settings opened |
| Valid form with key | Results: MAT_0154 Cardboard Boxes, score 81.6 (now shown under the form, see `docs/ui_integration.md`) |
| "Edit product" | All 7 values restored |
| Wine bottle, Drinkware, fragility 4, Sea | "No suitable material found", 0 candidates, table hidden |
| New tab, results page only | Labelled sample shown |
| Tablet width (768 px), all pages | No sideways scrolling |
| Browser console | No JavaScript errors |
