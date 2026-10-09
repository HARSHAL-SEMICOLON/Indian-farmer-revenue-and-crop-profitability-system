# Data dictionary

Generated from the SQLite database by `src/data_dictionary.py`. Prices are Rs per quintal (1 quintal = 100 kg) unless stated.
*Gross value* columns are estimates (production x price) and **not farmer income**.

## Tables

| Table | Type | Grain | Rows | Contents |
|---|---|---|---|---|
| [`dim_crop`](#dim_crop) | Dimension | one row per crop | 26 | Crop registry: names, groups, APY unit and the factor converting APY production to the MSP/price unit |
| [`dim_state`](#dim_state) | Dimension | one row per state/UT | 36 | States with region and the IMD subdivisions used for rainfall |
| [`dim_location`](#dim_location) | Dimension | one row per district | 760 | Districts as reported by DES APY |
| [`dim_year`](#dim_year) | Dimension | one row per crop year 1990-2026 | 37 | Crop (agricultural) years, marketing seasons, data-availability flags, CPI deflator |
| [`dim_market`](#dim_market) | Dimension | one row per mandi/APMC | 3,418 | Markets reporting prices |
| [`dim_date`](#dim_date) | Dimension | one row per price date | 67 | Calendar attributes of mandi price dates |
| [`fact_production`](#fact_production) | Fact | district x crop x crop year x season | 239,760 | DES APY area and production, cleaned |
| [`fact_district_crop_year`](#fact_district_crop_year) | Fact | district x crop x crop year | 199,125 | Seasons summed; gross value at MSP, real value and volume value |
| [`fact_state_crop_year`](#fact_state_crop_year) | Fact | state x crop x crop year | 11,479 | State totals with cost of cultivation, estimated profit, mandi valuation, rainfall and yield anomaly |
| [`fact_msp`](#fact_msp) | Fact | crop x crop year | 516 | Official MSP/FRP with bonus, CACP cost, real MSP and source URL |
| [`fact_market_price`](#fact_market_price) | Fact | market x crop x date (x variety) | 106,885 | Mandi prices from AGMARKNET and Maharashtra APMC, with the MSP that applied on the date |
| [`fact_cost_of_cultivation`](#fact_cost_of_cultivation) | Fact | state x crop x crop year | 300 | DES Cost of Cultivation Scheme estimates (2008-09 to 2013-14) |
| [`fact_weather_state`](#fact_weather_state) | Fact | state x year | 910 | Seasonal rainfall per state (mean of its IMD subdivisions) |
| [`fact_weather_subdivision`](#fact_weather_subdivision) | Fact | IMD subdivision x year | 4,116 | Monthly and seasonal rainfall as published by IMD |
| [`dq_issues`](#dq_issues) | Quality | one row per issue | 18 | Data problems found and how each was handled |
| [`dq_coverage`](#dq_coverage) | Quality | domain x member x metric | 67 | Coverage counts per dataset |
| [`dq_validation`](#dq_validation) | Quality | crop x check | 8 | Cleaned totals compared with independent official estimates |
| [`ref_sources`](#ref_sources) | Reference | one row per dataset | 9 | Source register: publisher, coverage, grain, URL, reliability note |

## dim_crop

Crop registry: names, groups, APY unit and the factor converting APY production to the MSP/price unit. Grain: one row per crop.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `crop_id` | Crop key (-> dim_crop) | ID | 1 |
| `crop_name` | Crop name | text | Rice |
| `apy_name` | Crop name as written in DES APY | text | Rice |
| `crop_group` | Cereals, Pulses, Oilseeds, Fibres, Cash crops, Horticulture, Spices | text | Cereals |
| `primary_season` | Main growing season (Kharif / Rabi / Whole year) | text | Kharif |
| `apy_unit` | Unit APY reports production in (tonnes; milled rice; 170-kg lint bales; 180-kg jute bales) | text | tonnes (milled rice) |
| `price_form` | Commodity form MSP is defined for (paddy, kapas, whole grain...) | text | Paddy (common), Rs/qtl |
| `to_price_qtl_factor` | Multiply APY production by this to get quintals of the MSP form (rice 10/0.67 = 14.93; cotton bale 1.7/0.34 = 5.0; tonnes x10) | factor | 14.925373134328357 |
| `msp_key` | MSP crop name used to join MSP | text | Paddy |
| `is_msp_crop` | 1 = government announces an MSP/FRP for this crop | 0/1 | 1 |

## dim_state

States with region and the IMD subdivisions used for rainfall. Grain: one row per state/UT.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `state_id` | State key (-> dim_state) | ID | 1 |
| `state_name` | State or UT | text | Andaman and Nicobar Islands |
| `region` | North / South / East / West / Central / North-East | text | East |
| `state_group` | State with its pre-2000/2014 parent merged (for consistent long trends) | text | Andaman and Nicobar Islands |
| `imd_subdivisions` | IMD meteorological subdivisions averaged for the state | text | ANDAMAN & NICOBAR ISLANDS |

## dim_location

Districts as reported by DES APY. Grain: one row per district.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `location_id` | District key (-> dim_location) | ID | 1 |
| `state_name` | State or UT | text | Andaman and Nicobar Islands |
| `district_name` | District | text | Nicobars |
| `state_id` | State key (-> dim_state) | ID | 1 |
| `district_key` | state|district natural key | text | Andaman and Nicobar Islands / Nicobars |
| `first_year` | First crop year the district reports | year | 2000 |
| `last_year` | Last crop year the district reports | year | 2019 |

## dim_year

Crop (agricultural) years, marketing seasons, data-availability flags, CPI deflator. Grain: one row per crop year 1990-2026.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `crop_year` | Crop (agricultural) year, first calendar year: 2016 = 2016-17 | year | 1990 |
| `crop_year_label` | Crop year as text, e.g. 2016-17 | text | 1990-91 |
| `kharif_marketing_season` | KMS that sells this crop year's kharif crop (Oct Y - Sep Y+1) | text | KMS 1990-91 |
| `rabi_marketing_season` | RMS that sells this crop year's rabi crop (Apr Y+1 - Mar Y+2) | text | RMS 1991-92 |
| `has_production_data` | APY production available | 0/1 | 0 |
| `in_msp_valuation_window` | Crop year inside the official MSP series used for valuation (2004-2026) | 0/1 | 0 |
| `is_provisional` | Provisional year (2019-20) | 0/1 | 0 |
| `has_cost_data` | DES cost data exist (2008-2013) | 0/1 | 0 |
| `has_rainfall_data` | Rainfall data exist (to 2015) | 0/1 | 0 |
| `cpi_deflator_2018_100` | CPI deflator, mean of calendar years Y and Y+1, 2018-19 = 100 (World Bank FP.CPI.TOTL) | index | 32.85055890008091 |
| `decade` | 5-year bucket | text | 1990-1994 |

## dim_market

Markets reporting prices. Grain: one row per mandi/APMC.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `market_id` | Market key (-> dim_market) | ID | 1 |
| `market_name` | Mandi / APMC name | text | Diglipur Vegetable Market (Subhashgram) |
| `district_name` | District | text | North And Middle Andaman |
| `state_name` | State or UT | text | Andaman and Nicobar Islands |
| `first_seen_in` | Price dataset where the market first appears | text | AGMARKNET daily Jul-Sep 2026 |
| `state_id` | State key (-> dim_state) | ID | 1 |

## dim_date

Calendar attributes of mandi price dates. Grain: one row per price date.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `date_key` | Date key YYYYMMDD (-> dim_date) | ID | 20140901 |
| `price_date` | Price date | date | 2014-09-01 |
| `year` | Calendar year | year | 2014 |
| `month` | Calendar month | 1-12 | 9 |
| `month_name` | Month name | text | Sep |
| `year_month` | YYYY-MM | text | 2014-09 |
| `agri_year` | Crop year the date falls in (Jul-Jun) | year | 2014 |
| `agri_year_label` | Crop year label | text | 2014-15 |
| `season_window` | Kharif window (Jun-Oct) / Rabi window (Nov-Mar) / other | text | Kharif window (Jun-Oct) |

## fact_production

DES APY area and production, cleaned. Grain: district x crop x crop year x season.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `production_id` | Row key | ID | 1 |
| `location_id` | District key (-> dim_location) | ID | 1 |
| `crop_id` | Crop key (-> dim_crop) | ID | 1 |
| `crop_year` | Crop (agricultural) year, first calendar year: 2016 = 2016-17 | year | 2000 |
| `season` | APY season (Kharif, Rabi, Whole Year, Summer, Autumn, Winter) | text | Kharif |
| `area_ha` | Area sown/harvested | hectares | 102.0 |
| `production_apy_unit` | Production in the APY unit (see dim_crop.apy_unit) | tonnes / bales | 321.0 |
| `production_price_qtl` | Production converted to the MSP commodity form | quintals | 4791.044776119403 |
| `yield_apy_unit_per_ha` | Production per hectare in APY unit | APY unit/ha | 3.147058823529412 |
| `dq_flag` | ok / flag: ... / excluded: ... (excluded rows are left out of analysis) | text | ok |

## fact_district_crop_year

Seasons summed; gross value at MSP, real value and volume value. Grain: district x crop x crop year.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `district_crop_year_id` | Row key | ID | 1 |
| `location_id` | District key (-> dim_location) | ID | 1 |
| `state_id` | State key (-> dim_state) | ID | 1 |
| `crop_id` | Crop key (-> dim_crop) | ID | 1 |
| `crop_name` | Crop name | text | Rice |
| `crop_year` | Crop (agricultural) year, first calendar year: 2016 = 2016-17 | year | 2000 |
| `area_ha` | Area sown/harvested | hectares | 102.0 |
| `production_apy_unit` | Production in the APY unit (see dim_crop.apy_unit) | tonnes / bales | 321.0 |
| `production_price_qtl` | Production converted to the MSP commodity form | quintals | 4791.044776119403 |
| `n_seasons` | Seasons summed into the row | count | 1 |
| `yield_kg_per_ha` | Yield (cotton: kg lint/ha; rice: kg milled rice/ha) | kg/ha | 3147.058823529412 |
| `msp_effective` | MSP + verified bonus for the crop year | Rs/qtl | 560.0 |
| `gross_value_msp_inr` | Estimated gross value = production_price_qtl x msp_effective. NOT farmer income | Rs | 610149.2537313432 |
| `gross_value_msp_per_ha` | Gross value at MSP per hectare | Rs/ha | 11525.297577093752 |
| `gross_value_at_2018_msp_inr` | Volume measure: production valued at constant 2018-19 MSP | Rs (2018-19 MSP) | 1906716.417910448 |
| `cpi_deflator_2018_100` | CPI deflator, mean of calendar years Y and Y+1, 2018-19 = 100 (World Bank FP.CPI.TOTL) | index | 32.85055890008091 |
| `gross_value_real_2018_inr` | Real value: gross value deflated by CPI to 2018-19 rupees | Rs (2018-19) | 1589401.9566167302 |
| `valuation_basis` | Why a row is or isn't valued (no MSP / outside window) | text | Not valued: outside MSP window (2004-202… |
| `is_provisional_year` | Provisional year (2019-20) | 0/1 | 0 |

## fact_state_crop_year

State totals with cost of cultivation, estimated profit, mandi valuation, rainfall and yield anomaly. Grain: state x crop x crop year.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `state_crop_year_id` | Row key | ID | 1 |
| `state_id` | State key (-> dim_state) | ID | 1 |
| `crop_id` | Crop key (-> dim_crop) | ID | 1 |
| `crop_year` | Crop (agricultural) year, first calendar year: 2016 = 2016-17 | year | 2000 |
| `area_ha` | Area sown/harvested | hectares | 10881.0 |
| `production_apy_unit` | Production in the APY unit (see dim_crop.apy_unit) | tonnes / bales | 32184.0 |
| `production_price_qtl` | Production converted to the MSP commodity form | quintals | 480358.2089552239 |
| `gross_value_msp_inr` | Estimated gross value = production_price_qtl x msp_effective. NOT farmer income | Rs | 244001194.02985072 |
| `n_districts` | Districts summed into the row | count | 2 |
| `crop_name` | Crop name | text | Rice |
| `state_name` | State or UT | text | Andaman and Nicobar Islands |
| `yield_kg_per_ha` | Yield (cotton: kg lint/ha; rice: kg milled rice/ha) | kg/ha | 2957.816377171216 |
| `yield_price_qtl_per_ha` | Yield in the MSP commodity form | qtl/ha | 44.1465130921077 |
| `msp_effective` | MSP + verified bonus for the crop year | Rs/qtl | 560.0 |
| `gross_value_msp_per_ha` | Gross value at MSP per hectare | Rs/ha | 22729.67046143341 |
| `a2fl_per_ha` | DES cost A2+FL: paid-out costs + imputed family labour | Rs/ha | 29664.84 |
| `c2_per_ha` | DES cost C2: comprehensive, incl. imputed rent and interest on owned land/capital | Rs/ha | 46450.2 |
| `c2_per_qtl` | C2 cost per quintal of main product | Rs/qtl | 789.9 |
| `implied_yield_qtl_per_ha` | Yield implied by DES cost survey (C2/ha / C2/qtl) | qtl/ha | 58.80516521078617 |
| `has_official_cost` | DES cost exists for this state x crop x year | 0/1 | 0 |
| `est_profit_a2fl_per_ha` | Gross value at MSP per ha - A2+FL per ha | Rs/ha | 11516.421715517874 |
| `est_profit_c2_per_ha` | Gross value at MSP per ha - C2 per ha | Rs/ha | -5268.938284482123 |
| `est_profit_c2_per_acre` | Estimated profit over C2 per acre | Rs/acre | -2132.2655585939324 |
| `msp_minus_c2_per_qtl` | MSP - C2 cost per quintal | Rs/qtl | 60.10000000000002 |
| `est_margin_c2_pct` | Profit over C2 / C2 cost | % | -12.79450425992336 |
| `apy_vs_coc_yield_ratio` | APY yield / cost-survey yield (bias check) | ratio | 0.8238824433374836 |
| `mandi_awm_price` | Arrival-weighted mandi modal price (Maharashtra 2014-15) | Rs/qtl |  |
| `months_observed` | Months of mandi data behind mandi_awm_price | count |  |
| `gross_value_mandi_inr` | Production x mandi price (Maharashtra 2014-15 only) | Rs |  |
| `mandi_vs_msp_pct` | Mandi price vs MSP | % |  |
| `jjas_mm` | Monsoon (Jun-Sep) rainfall | mm | 1244.1999999999998 |
| `jjas_dep_pct` | Monsoon departure from normal | % | -25.60036356678148 |
| `jjas_category` | IMD category: Large excess / Excess / Normal / Deficient / Large deficient | text | Deficient |
| `rabi_rain_mm` | Rabi-season rainfall (Oct-Dec + Jan-Feb next year) | mm | 699.4000000000001 |
| `rabi_rain_dep_pct` | Rabi rainfall departure from normal | % | -8.31629175187456 |
| `rainfall_basis` | How state rainfall was built (subdivision mean) | text | Single IMD subdivision (may be shared wi… |
| `rain_metric` | Rain metric matched to the crop's season | text | Monsoon (Jun-Sep) |
| `season_rain_dep_pct` | Departure of the season-matched rainfall | % | -25.60036356678148 |
| `yield_trend_kg_per_ha` | Linear-trend yield for the state x crop | kg/ha | 2662.932838388806 |
| `yield_anomaly_pct` | Yield vs its own linear trend (detrended) | % | -8.698799851707662 |
| `is_provisional_year` | Provisional year (2019-20) | 0/1 | 0 |

## fact_msp

Official MSP/FRP with bonus, CACP cost, real MSP and source URL. Grain: crop x crop year.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `msp_id` | Row key | ID | 1 |
| `crop_id` | Crop key (-> dim_crop) | ID | 5 |
| `msp_key` | MSP crop name used to join MSP | text | Bajra |
| `crop_year` | Crop (agricultural) year, first calendar year: 2016 = 2016-17 | year | 2002 |
| `crop_year_label` | Crop year as text, e.g. 2016-17 | text | 2002-03 |
| `marketing_season` | Marketing season the MSP applies to (KMS / RMS) | text | KMS 2002-03 |
| `season` | APY season (Kharif, Rabi, Whole Year, Summer, Autumn, Winter) | text | Kharif |
| `variety` | Variety / grade | text | FAQ |
| `msp_base` | Announced MSP / FRP | Rs/qtl | 495.0 |
| `bonus` | State/central bonus over MSP (NULL = not verified) | Rs/qtl | 0.0 |
| `bonus_verified` | Bonus confirmed in an official source | 0/1 | 1 |
| `msp_effective` | MSP + verified bonus for the crop year | Rs/qtl | 495.0 |
| `a2fl_cost` | CACP projected all-India A2+FL cost | Rs/qtl | 949.0 |
| `msp_over_a2fl_pct` | MSP margin over A2+FL | % | 50.15806111696524 |
| `msp_real_2018` | MSP in constant 2018-19 rupees (msp_effective / CPI deflator x 100) | Rs/qtl (2018-19) | 1391.9468892103237 |
| `source_id` | Source key (see ref_sources / curated source list) | text | OGD_2002_12 |
| `source_title` | Source document | text | data.gov.in - Minimum Support Prices of … |
| `source_url` | URL of the official release | url | https://www.data.gov.in/ |
| `verification` | official / secondary | text | official |
| `note` | Note | text | Bonus treatment as published by source (… |

## fact_market_price

Mandi prices from AGMARKNET and Maharashtra APMC, with the MSP that applied on the date. Grain: market x crop x date (x variety).

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `price_id` | Row key | ID | 1 |
| `market_id` | Market key (-> dim_market) | ID | 5 |
| `crop_id` | Crop key (-> dim_crop) | ID | 1 |
| `date_key` | Date key YYYYMMDD (-> dim_date) | ID | 20260723 |
| `source_dataset` | Price dataset (MH APMC monthly 2014-16 / AGMARKNET 30-Sep-2024 / AGMARKNET Jul-Sep 2026) | text | AGMARKNET daily Jul-Sep 2026 |
| `granularity` | Monthly or Daily | text | Daily |
| `commodity_raw` | Commodity label as published | text | Paddy(Common) |
| `variety` | Variety / grade | text | Paddy |
| `price_form` | Commodity form of the quote (paddy, milled rice, kapas, dal...) | text | Paddy (common) |
| `msp_comparable` | Form matches the MSP form (only these are compared with MSP) | 0/1 | 1 |
| `arrivals_qtl` | Market arrivals (Maharashtra only) | quintals |  |
| `min_price` | Minimum price | Rs/qtl | 2200.0 |
| `max_price` | Maximum price | Rs/qtl | 2400.0 |
| `modal_price` | Modal (most common) price | Rs/qtl | 2300.0 |
| `price_spread` | max - min | Rs/qtl | 200.0 |
| `price_spread_pct` | (max - min) / modal | % | 8.695652173913043 |
| `msp_crop_year` | Crop year whose MSP applies on the price date (marketing-season rule) | year | 2025 |
| `msp_applicable` | MSP in force on the price date | Rs/qtl | 2369.0 |
| `modal_vs_msp_pct` | Modal price vs MSP | % | -2.9126213592233 |
| `modal_below_msp` | Modal price < MSP | 0/1 | 1 |
| `msp_price_band` | Distance from MSP bucket (>20% below ... >10% above) | text | 0-10% below |
| `msp_price_band_order` | Sort order of msp_price_band | 1-5 | 3 |
| `dq_flag` | ok / flag: ... / excluded: ... (excluded rows are left out of analysis) | text | ok |

## fact_cost_of_cultivation

DES Cost of Cultivation Scheme estimates (2008-09 to 2013-14). Grain: state x crop x crop year.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `cost_id` | Row key | ID | 1 |
| `crop_name` | Crop name | text | Arhar/Tur |
| `state_name` | State or UT | text | Andhra Pradesh |
| `crop_year` | Crop (agricultural) year, first calendar year: 2016 = 2016-17 | year | 2008 |
| `a2fl_per_ha` | DES cost A2+FL: paid-out costs + imputed family labour | Rs/ha | 17051.66 |
| `c2_per_ha` | DES cost C2: comprehensive, incl. imputed rent and interest on owned land/capital | Rs/ha | 24171.65 |
| `c2_per_qtl` | C2 cost per quintal of main product | Rs/qtl | 3670.54 |
| `implied_yield_qtl_per_ha` | Yield implied by DES cost survey (C2/ha / C2/qtl) | qtl/ha | 6.585311698006288 |
| `crop_year_label` | Crop year as text, e.g. 2016-17 | text | 2008-09 |
| `crop_id` | Crop key (-> dim_crop) | ID | 9 |
| `state_id` | State key (-> dim_state) | ID | 2 |
| `source` | Source dataset | text | DES/CACP Cost of Cultivation Scheme via … |

## fact_weather_state

Seasonal rainfall per state (mean of its IMD subdivisions). Grain: state x year.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `state_weather_id` | Row key | ID | 1 |
| `crop_year` | Crop (agricultural) year, first calendar year: 2016 = 2016-17 | year | 1990 |
| `jjas_mm` | Monsoon (Jun-Sep) rainfall | mm | 1107.9 |
| `rabi_rain_mm` | Rabi-season rainfall (Oct-Dec + Jan-Feb next year) | mm | 542.9 |
| `annual_mm` | Annual rainfall | mm | 2183.2 |
| `jjas_normal_mm` | 1951-2000 mean monsoon rainfall of this series | mm | 1672.32 |
| `rabi_rain_normal_mm` | 1951-2000 mean rabi rainfall | mm | 762.84 |
| `annual_normal_mm` | 1951-2000 mean annual rainfall | mm | 2892.506 |
| `state_name` | State or UT | text | Andaman and Nicobar Islands |
| `n_subdivisions` | IMD subdivisions averaged | count | 1 |
| `jjas_dep_pct` | Monsoon departure from normal | % | -33.750717566016064 |
| `rabi_rain_dep_pct` | Rabi rainfall departure from normal | % | -28.83173404645798 |
| `annual_dep_pct` | Annual departure from normal | % | -24.522196323879708 |
| `jjas_category` | IMD category: Large excess / Excess / Normal / Deficient / Large deficient | text | Deficient |
| `rainfall_basis` | How state rainfall was built (subdivision mean) | text | Single IMD subdivision (may be shared wi… |
| `state_id` | State key (-> dim_state) | ID | 1 |

## fact_weather_subdivision

Monthly and seasonal rainfall as published by IMD. Grain: IMD subdivision x year.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `weather_id` | Row key | ID | 1 |
| `subdivision` | IMD meteorological subdivision | text | ANDAMAN & NICOBAR ISLANDS |
| `year` | Calendar year | year | 1901 |
| `JAN` | Jan rainfall | mm | 49.2 |
| `FEB` | Feb rainfall | mm | 87.1 |
| `MAR` | Mar rainfall | mm | 29.2 |
| `APR` | Apr rainfall | mm | 2.3 |
| `MAY` | May rainfall | mm | 528.8 |
| `JUN` | Jun rainfall | mm | 517.5 |
| `JUL` | Jul rainfall | mm | 365.1 |
| `AUG` | Aug rainfall | mm | 481.1 |
| `SEP` | Sep rainfall | mm | 332.6 |
| `OCT` | Oct rainfall | mm | 388.5 |
| `NOV` | Nov rainfall | mm | 558.2 |
| `DEC` | Dec rainfall | mm | 33.6 |
| `jjas_mm` | Monsoon (Jun-Sep) rainfall | mm | 1696.3000000000002 |
| `ond_mm` | Oct-Dec rainfall | mm | 980.3 |
| `rabi_rain_mm` | Rabi-season rainfall (Oct-Dec + Jan-Feb next year) | mm | 1140.1 |
| `annual_mm` | Annual rainfall | mm | 3373.2000000000003 |
| `jjas_normal_mm` | 1951-2000 mean monsoon rainfall of this series | mm | 1672.32 |
| `jjas_dep_pct` | Monsoon departure from normal | % | 1.433936088786858 |
| `jjas_category` | IMD category: Large excess / Excess / Normal / Deficient / Large deficient | text | Normal |
| `rabi_rain_normal_mm` | 1951-2000 mean rabi rainfall | mm | 762.84 |
| `rabi_rain_dep_pct` | Rabi rainfall departure from normal | % | 49.454669393319705 |
| `annual_normal_mm` | 1951-2000 mean annual rainfall | mm | 2892.506 |
| `annual_dep_pct` | Annual departure from normal | % | 16.618599926845445 |

## dq_issues

Data problems found and how each was handled. Grain: one row per issue.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `issue_id` | Row key | ID | 1 |
| `domain` | Area of the data | text | Production (APY) |
| `issue` | Problem found | text | Crop year 2020 reported by only 13 distr… |
| `action` | How it was handled | text | excluded |
| `n_rows` | Rows affected | count | 219 |
| `detail` | Detail | text | AGMARKNET daily snapshot 30-Sep-2024 |

## dq_coverage

Coverage counts per dataset. Grain: domain x member x metric.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `domain` | Area of the data | text | Production |
| `dimension` | Coverage dimension | text | crop_year |
| `member` | Coverage member | text | 1997 |
| `metric` | Coverage metric | text | rows |
| `value` | Metric value | number | 6772.0 |

## dq_validation

Cleaned totals compared with independent official estimates. Grain: crop x check.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `check_name` | Validation check | text | District sum vs DES all-India estimate |
| `crop_name` | Crop name | text | Rice |
| `crop_year` | Crop (agricultural) year, first calendar year: 2016 = 2016-17 | year | 2019 |
| `dataset_value` | Value from this project | unit column | 132.11 |
| `official_value` | Independent official value | unit column | 117.94 |
| `unit` | Unit of the two values | text | million tonnes |
| `diff_pct` | dataset vs official | % | 12.0 |
| `official_source` | Official source and URL | text | PIB 3rd Advance Estimates 2019-20, https… |
| `status` | consistent (within 10%) / divergent | text | divergent (>10%) |

## ref_sources

Source register: publisher, coverage, grain, URL, reliability note. Grain: one row per dataset.

| Column | Meaning | Unit | Example |
|---|---|---|---|
| `source_id` | Source key (see ref_sources / curated source list) | text | APY |
| `dataset` | Dataset name | text | District-wise, season-wise crop producti… |
| `publisher` | Publisher | text | DES, Ministry of Agriculture & FW (via d… |
| `coverage` | Time / space coverage | text | 1997-98 to 2019-20 |
| `grain` | Row grain | text | District x season x crop |
| `used_for` | Used for | text | Production, area, yield |
| `access_route` | How it was obtained | text | Mirror github.com/Aditya12084/Crop-Stati… |
| `url` | URL | url | https://www.data.gov.in/catalog/district… |
| `reliability_note` | Known limitations | text | District sums diverge from DES all-India… |
