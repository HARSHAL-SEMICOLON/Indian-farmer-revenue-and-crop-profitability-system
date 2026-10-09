# Power BI build guide — Indian Farmer Revenue, Crop Profitability & Market Intelligence

Everything the report needs is in `power_bi/data/` (CSV star schema), `power_bi/dax_measures.dax`,
`power_bi/power_query_load.pq` and `power_bi/theme_agri_intel.json`. Build time ≈ 2–3 hours.

---

## 1. Load the data (15 min)

1. **Home → Transform data → Manage Parameters → New**: `ExportFolder` (Text) =
   `E:\DA PROJECTS\Indian Farmer Revenue Intelligence\power_bi\data\` (keep the trailing `\`).
2. **New Source → Blank Query** → Advanced Editor → paste `power_query_load.pq` → name it `fnLoad`.
3. For each table below: **New Source → Blank Query** → formula `= fnLoad("dim_crop")` → rename the query to the table name.

| Load | Tables |
|---|---|
| Dimensions | `dim_crop`, `dim_state`, `dim_location`, `dim_year`, `dim_market`, `dim_date` |
| Facts | `fact_district_crop_year`, `fact_state_crop_year`, `fact_msp`, `fact_market_price`, `fact_cost_of_cultivation`, `fact_weather_state` |
| Data quality | `dq_issues`, `dq_coverage`, `dq_validation`, `ref_sources` |
| Optional helpers | `agg_q04b_value_growth_decomposition`, `agg_q07a_rain_yield_association`, `agg_q10a_market_volatility_mh`, `agg_q05a_cross_market_dispersion_2024` |

`fact_production` (season grain, 240k rows) is optional. The report uses the annual `fact_district_crop_year`.

4. **View → Themes → Browse for themes** → `theme_agri_intel.json`.

## 2. Model relationships (Model view)

All are **many-to-one, single direction** (dimension filters fact). Mark `dim_date[price_date]` as a date table if you want time intelligence on prices.

| From (many) | To (one) |
|---|---|
| `fact_district_crop_year[location_id]` | `dim_location[location_id]` |
| `fact_district_crop_year[crop_id]` | `dim_crop[crop_id]` |
| `fact_district_crop_year[crop_year]` | `dim_year[crop_year]` |
| `dim_location[state_id]` | `dim_state[state_id]` |
| `fact_state_crop_year[state_id]` | `dim_state[state_id]` |
| `fact_state_crop_year[crop_id]` | `dim_crop[crop_id]` |
| `fact_state_crop_year[crop_year]` | `dim_year[crop_year]` |
| `fact_msp[crop_id]` | `dim_crop[crop_id]` |
| `fact_msp[crop_year]` | `dim_year[crop_year]` |
| `fact_market_price[market_id]` | `dim_market[market_id]` |
| `fact_market_price[crop_id]` | `dim_crop[crop_id]` |
| `fact_market_price[date_key]` | `dim_date[date_key]` |
| `dim_market[state_id]` | `dim_state[state_id]` |
| `fact_cost_of_cultivation[crop_id]` / `[state_id]` / `[crop_year]` | `dim_crop` / `dim_state` / `dim_year` |
| `fact_weather_state[state_id]` / `[crop_year]` | `dim_state` / `dim_year` |

> `fact_district_crop_year` also has a `state_id` column. **Do not** relate it, because filtering already flows `dim_state → dim_location → fact`, and a second path would make the model ambiguous.

Hide all `*_id` / `*_key` columns in report view. Sort `dim_date[month_name]` by `dim_date[month]`.

## 3. Measures

Create a table `_Measures` (Home → Enter data → OK), then paste each measure from `dax_measures.dax`
(one measure per *New measure*). Formats:

* `Rs cr` measures → Whole number, thousands separator
* `% ` measures → Percentage, 1 decimal
* `per ha` / `per acre` / `Rs/qtl` → Whole number

## 4. Global design rules

* Canvas 16:9, background from theme. Top band (height 60px): title text, then **`[Value Disclaimer]`** in a small card. It must appear on pages 1–3.
* Sync these slicers across pages 1–3 and 5 (View → Sync slicers): `dim_year[crop_year]` (between-slider, default **2004–2018**), `dim_crop[crop_group]`, `dim_crop[crop_name]`, `dim_state[region]`, `dim_state[state_name]`.
* Add page-level filter `dim_crop[is_msp_crop] = 1` on pages 1–3 (non-MSP crops are not valued).
* Use the word **"Estimated gross value @ MSP"** everywhere. Never use "income" or "revenue earned by farmers".

---

## Page 1 — Executive Agricultural Overview

| Visual | Fields |
|---|---|
| KPI cards ×6 | `Gross Value @ MSP (Rs cr)`, `Area (M ha)`, `Gross Value @ MSP per ha (Rs)`, `Gross Value CAGR %`, `Districts Covered`, `Valuation Coverage %` |
| Line chart: *Nominal vs volume* | X `dim_year[crop_year]`; Y `Gross Value @ MSP (Rs cr)` and `Gross Value @ 2018 MSP (Rs cr)` |
| Treemap: *Value mix by crop group → crop* | Group `dim_crop[crop_group]`, `dim_crop[crop_name]`; Values `Gross Value @ MSP (Rs cr)` |
| Filled map or bar: *Value by state* | Location `dim_state[state_name]` (set Data category = State or Province, add ", India" via a calculated column if needed); Color saturation `Gross Value @ MSP per ha (Rs)` |
| Card | `Provisional Year Flag` (shows only when 2019 is selected) |
| Text box | "Volume line values every year at 2018-19 MSP, so the gap between lines = MSP increases." |

**Insight to annotate:** nominal value rose ~4.5× between 2004-05 and 2018-19, while volume (at constant 2018-19 MSP) rose only ~1.4×. Most of the growth is MSP increases.

## Page 2 — Crop Revenue & Profitability

| Visual | Fields |
|---|---|
| Clustered bar: *Top crops by est. gross value* | Y `dim_crop[crop_name]`; X `Gross Value @ MSP (Rs cr)`; Top N 12 |
| Bar: *Gross value per ha* | Y `crop_name`; X `Gross Value @ MSP per ha (Rs)` |
| **Scatter: footprint vs value/ha (Q8)** | X `Area (M ha)`; Y `Gross Value @ MSP per ha (Rs)`; Size `Gross Value @ MSP (Rs cr)`; Legend `crop_group`; Details `crop_name`. Add X/Y average lines for quadrants |
| Table: *Profit where costs exist (Q2)* | Rows `crop_name`; `Gross Value @ MSP per ha (Rs)`, `A2+FL Cost per ha (Rs)`, `C2 Cost per ha (Rs)`, `Est. Profit over A2+FL per ha (Rs)`, `Est. Profit over C2 per ha (Rs)`, `Est. Profit over C2 per acre (Rs)`, `State-years with C2 Loss %`. Conditional formatting (red < 0). **Visual-level filter `dim_year[crop_year]` 2008–2013** |
| Card | `Profit Data Available` |
| Line: *MSP vs CACP A2+FL cost* | X `crop_year`; Y `MSP (Rs/qtl)`, `CACP A2+FL Cost (Rs/qtl)` (single-crop slicer) |
| Stacked bar (helper table): *Value growth decomposition (Q4)* | `agg_q04b_value_growth_decomposition`: Y `crop_name`; X `area_contribution_pct`, `yield_contribution_pct`, `price_msp_contribution_pct` (100% stacked) |

**Note box:** "Profit = APY yield × MSP − DES cost/ha, for 10 crops in surveyed states 2008-09 to 2013-14 only. Valuing at MSP understates crops whose market price exceeded MSP (e.g. pulses and cotton in several years). This is not farmer income."

## Page 3 — State / District Analysis

| Visual | Fields |
|---|---|
| Matrix heatmap | Rows `dim_state[state_name]`; Columns `dim_crop[crop_name]`; Values `Gross Value @ MSP per ha (Rs)`, background colour scale |
| Bar: *State ranking* | `state_name` × `Gross Value @ MSP per ha (Rs)` (filter: `MSP-valued Area (ha)` > 100,000) |
| Table: *Top districts* | `dim_location[state_name]`, `district_name`, `Gross Value @ MSP per ha (Rs)`, `Gross Value @ MSP (Rs cr)`, `MSP-valued Area (ha)`. Top N 20 by value/ha with area > 50,000 |
| Line: *State yield trend* | X `crop_year`; Y `Yield (kg/ha)`; Legend `state_name` (single-crop slicer, top 6 states) |
| Toggle (bookmark) | Switch `state_name` ↔ `state_group` to merge AP+Telangana, MP+Chhattisgarh, etc. for consistent trends |
| Drill-through page (hidden) | Drill on `district_name`: crop mix donut, yield trend, value trend |

## Page 4 — Mandi Price Intelligence

Slicers: `fact_market_price[source_dataset]` (single select; default *MH APMC monthly*), `dim_crop[crop_name]`, `fact_market_price[price_form]`, `dim_market[state_name]`.

| Visual | Fields |
|---|---|
| KPI cards | `Arrival-wtd Modal Price (Rs/qtl)`, `Applicable MSP (Rs/qtl)`, `Quotes below MSP %`, `Arrivals below MSP %`, `Modal Price CV %`, `Markets Reporting` |
| Line: *Monthly price vs MSP (MH 2014-16)* | X `dim_date[year_month]`; Y `Arrival-wtd Modal Price`, `Applicable MSP` |
| Bar: *% quotes below MSP by crop (Q6)* | Y `crop_name`; X `Quotes below MSP %`; filter `msp_comparable = 1` |
| Box-style: *Cross-market dispersion (Q5)* | Use the helper `agg_q05a_cross_market_dispersion_2024` → table with p25/median/p75/min/max + `cv_pct`, or a scatter of `dim_market[market_name]` × `Avg Modal Price` by state |
| Table: *Most volatile markets (Q10)* | `agg_q10a_market_volatility_mh`: market, crop, months, `cv_pct`, `max_min_ratio`, `mean_abs_mom_change_pct`; Top N 20 by CV |
| Map (optional) | `dim_market[district_name]`, `state_name`; size `Valid Quotes` |

**Note box:** "MSP comparison only for MSP-comparable forms (FAQ paddy, kapas, whole grain). Milled rice, basmati, dal and ginned cotton are excluded. MSP applies by marketing season: kharif Oct–Sep, rabi Apr–Mar."

## Page 5 — Weather / Yield Analysis

| Visual | Fields |
|---|---|
| Cards | `Rain-Yield Correlation (r)`, `Rain-Yield Pairs (n)`, `Monsoon Departure %`, `Deficient-Rain Years` |
| **Scatter (Q7)** | X `fact_state_crop_year[season_rain_dep_pct]` (Don't summarize); Y `yield_anomaly_pct`; Details `state_name`, `crop_year`; Legend `crop_name`; trend line on. Visual filter year ≤ 2015 |
| Bar (helper): *Correlation by crop* | `agg_q07a_rain_yield_association`: `crop_name` × `pearson_r`, colour by `significant_5pct` |
| Column: *Avg yield anomaly by IMD rainfall category* | X `fact_state_crop_year[jjas_category]`; Y `Yield Anomaly %` |
| Line: *State monsoon departure* | X `crop_year`; Y `Monsoon Departure %`; constant lines at ±19% |

**Mandatory note:** "Correlation of detrended yield with rainfall departure, 1997-2015. Association only: irrigation, prices, pests, technology and sowing area also vary. State rainfall = mean of IMD subdivisions."

## Page 6 — Data Quality

| Visual | Fields |
|---|---|
| Cards | `Production Rows`, `Rows Excluded/Flagged`, `Validation Checks Divergent`, `MSP Values Official %` |
| Table | `dq_issues`: domain, issue, action, n_rows, detail |
| Clustered bar: *District sums vs DES estimates 2019-20* | `dq_validation`: crop_name × dataset_value, official_value; tooltip diff_pct, status |
| Line: *Coverage by year* | `dq_coverage` filtered metric = `districts` (X member, Y value) and `share_rows_msp_valued` |
| Table | `ref_sources` (dataset, publisher, coverage, access_route, reliability_note) |
| Matrix: *MSP provenance* | `fact_msp`: rows `msp_key`, columns `crop_year`, values `msp_effective`; conditional font colour on `verification` |

---

### Checklist before publishing
- [ ] No visual title or label uses the word "income"
- [ ] Profit visuals filtered to 2008–2013 and show the cost-coverage card
- [ ] 2019-20 flagged; default year slider 2004–2018
- [ ] Rain page notes association ≠ causation
- [ ] Mandi page shows which dataset is selected (single-select slicer)
