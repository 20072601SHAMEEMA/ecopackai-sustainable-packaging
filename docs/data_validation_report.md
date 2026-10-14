# Data Validation Report — EcoPackAI

Summary of data quality checks performed on the two raw datasets provided
for this project, and the cleaning steps applied before database ingestion.

## Source Files

| File | Rows (raw) | Rows (cleaned) | Columns |
|---|---|---|---|
| `EcoPackAI_dataset.csv` (materials) | 404 | 403 | 23 |
| `product_dataset.csv` (products) | 1500 | 1500 | 6 |

## Materials Dataset — Findings

1. **Incomplete row.** One row (`MAT_0404`) had 14 of 23 columns missing —
   looked like a truncated/incomplete entry at the end of the file.
   **Action:** dropped this row rather than imputing 14 missing values,
   since there wasn't enough information left in that row to reconstruct
   it reliably.

2. **Inconsistent column naming.** Raw headers used mixed case, spaces,
   percent signs and units embedded in the name (e.g. `Cost per Unit (USD)`,
   `Recyclability (%)`). **Action:** converted every column to snake_case
   (e.g. `cost_per_unit_usd`, `recyclability_percent`) to match standard
   database naming conventions.

3. **Extreme outlier in `biodegradation_time_days`.** Values range from
   31 days up to 180,208 days (~494 years). The high end corresponds to
   Steel, which genuinely takes centuries to biodegrade, so this is a
   real value, not a data error. **Action:** kept the value as-is, but
   flagged it for the ML modeling stage — a raw linear feature this skewed
   will need a log transform or similar before being fed into a model,
   otherwise it will dominate distance/impurity calculations disproportionately.

4. **No duplicate `material_id` values found.**

5. **Material type distribution is imbalanced:** Plastic (199), Cardboard
   (139), Paper/Bio-Based (37), Steel (29). This is worth being aware of
   for model training — Steel and Paper/Bio-Based have far fewer examples,
   so predictions for those material types will likely be less reliable.

## Products Dataset — Findings

1. **Inconsistent category values.** The `category` column contained both
   `"Cosmetics"` and `" Cosmetics"` (leading whitespace) as if they were
   two different categories. **Action:** stripped whitespace from all
   category values, merging them into a single consistent category.

2. **No duplicate `product_id` values found.**

3. **No missing values found** in any column.

4. **Category distribution:** Food (343), Electronics (294), Cosmetics
   (272 after merge), Paper Product (231), Pharmacy (208), Drinkware (148).
   Reasonably balanced across categories.

5. **Shipping type distribution:** Road (928), Air (465), Sea (107).

## Schema Note

The original `schema.sql` (written from the generic project brief before
real data was available) did not match the columns actually present in
the provided datasets. The schema was revised to reflect the real
dataset's columns exactly, rather than force-fitting the data into a
generic template. See `schema.sql` (v2) and `data_dictionary.md` (v2)
for the updated structure.

## Result

Both cleaned files were written to `data/processed/` (`materials.csv`,
`products.csv`) and their columns were verified to match `schema.sql`
exactly before ingestion.