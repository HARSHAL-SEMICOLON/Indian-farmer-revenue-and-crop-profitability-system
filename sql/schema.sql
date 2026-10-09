-- =====================================================================================
-- Indian Farmer Revenue, Crop Profitability & Market Intelligence System
-- SQLite star schema (v2 - rebuilt on official sources; see docs/METHODOLOGY.md)
--
-- Grain summary
--   fact_production            district x crop x crop_year x season       (DES APY)
--   fact_district_crop_year    district x crop x crop_year                (derived, MSP-valued)
--   fact_state_crop_year       state x crop x crop_year                   (derived + cost + rain)
--   fact_msp                   crop x crop_year                           (official MSP / FRP)
--   fact_market_price          market x commodity-form x date             (APMC / AGMARKNET)
--   fact_cost_of_cultivation   state x crop x crop_year                   (DES CoC, 2008-13)
--   fact_weather_subdivision   IMD subdivision x year                     (IMD)
--   fact_weather_state         state x year                               (derived from IMD)
-- crop_year = first year of agricultural year (2016 = 2016-17).
-- =====================================================================================
PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS vw_crop_revenue_summary;
DROP VIEW IF EXISTS vw_state_economics;
DROP VIEW IF EXISTS vw_mandi_msp_comparison;
DROP VIEW IF EXISTS vw_market_volatility;
DROP TABLE IF EXISTS ref_sources;
DROP TABLE IF EXISTS dq_validation;
DROP TABLE IF EXISTS dq_issues;
DROP TABLE IF EXISTS dq_coverage;
DROP TABLE IF EXISTS fact_weather_state;
DROP TABLE IF EXISTS fact_weather_subdivision;
DROP TABLE IF EXISTS fact_cost_of_cultivation;
DROP TABLE IF EXISTS fact_market_price;
DROP TABLE IF EXISTS fact_msp;
DROP TABLE IF EXISTS fact_state_crop_year;
DROP TABLE IF EXISTS fact_district_crop_year;
DROP TABLE IF EXISTS fact_production;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_market;
DROP TABLE IF EXISTS dim_year;
DROP TABLE IF EXISTS dim_location;
DROP TABLE IF EXISTS dim_state;
DROP TABLE IF EXISTS dim_crop;

CREATE TABLE dim_crop (
    crop_id              INTEGER PRIMARY KEY,
    crop_name            TEXT NOT NULL UNIQUE,
    apy_name             TEXT NOT NULL,           -- label in DES APY file
    crop_group           TEXT NOT NULL,
    primary_season       TEXT NOT NULL,
    apy_unit             TEXT NOT NULL,           -- unit of production in APY
    price_form           TEXT,                    -- commodity form MSP/mandi price refers to
    to_price_qtl_factor  REAL NOT NULL,           -- APY unit -> quintals of price_form
    msp_key              TEXT,                    -- NULL = not an MSP-mandated crop
    is_msp_crop          INTEGER NOT NULL
);

CREATE TABLE dim_state (
    state_id          INTEGER PRIMARY KEY,
    state_name        TEXT NOT NULL UNIQUE,
    region            TEXT NOT NULL,
    state_group       TEXT NOT NULL,               -- merges states split during 1997-2019
    imd_subdivisions  TEXT
);

CREATE TABLE dim_location (
    location_id    INTEGER PRIMARY KEY,
    state_name     TEXT NOT NULL,
    district_name  TEXT NOT NULL,
    state_id       INTEGER NOT NULL REFERENCES dim_state(state_id),
    district_key   TEXT NOT NULL UNIQUE,
    first_year     INTEGER,
    last_year      INTEGER
);
CREATE INDEX ix_loc_state ON dim_location(state_id);

CREATE TABLE dim_year (
    crop_year                INTEGER PRIMARY KEY,
    crop_year_label          TEXT NOT NULL,
    kharif_marketing_season  TEXT,
    rabi_marketing_season    TEXT,
    has_production_data      INTEGER,
    in_msp_valuation_window  INTEGER,
    is_provisional           INTEGER,
    has_cost_data            INTEGER,
    has_rainfall_data        INTEGER,
    cpi_deflator_2018_100    REAL,                -- World Bank CPI, mean of calendar Y and Y+1, 2018-19 = 100
    decade                   TEXT
);

CREATE TABLE dim_market (
    market_id      INTEGER PRIMARY KEY,
    market_name    TEXT NOT NULL,
    district_name  TEXT,
    state_name     TEXT NOT NULL,
    first_seen_in  TEXT,
    state_id       INTEGER REFERENCES dim_state(state_id)
);
CREATE INDEX ix_mkt_state ON dim_market(state_name);

CREATE TABLE dim_date (
    date_key        INTEGER PRIMARY KEY,           -- yyyymmdd
    price_date      TEXT NOT NULL,
    year            INTEGER, month INTEGER, month_name TEXT, year_month TEXT,
    agri_year       INTEGER, agri_year_label TEXT, season_window TEXT
);

CREATE TABLE fact_production (
    production_id          INTEGER PRIMARY KEY,
    location_id            INTEGER NOT NULL REFERENCES dim_location(location_id),
    crop_id                INTEGER NOT NULL REFERENCES dim_crop(crop_id),
    crop_year              INTEGER NOT NULL REFERENCES dim_year(crop_year),
    season                 TEXT NOT NULL,
    area_ha                REAL NOT NULL,
    production_apy_unit    REAL NOT NULL,          -- as reported (t, or bales)
    production_price_qtl   REAL NOT NULL,          -- converted to price_form quintals
    yield_apy_unit_per_ha  REAL,
    dq_flag                TEXT
);
CREATE INDEX ix_prod_crop_year ON fact_production(crop_id, crop_year);
CREATE INDEX ix_prod_loc ON fact_production(location_id);

CREATE TABLE fact_district_crop_year (
    district_crop_year_id   INTEGER PRIMARY KEY,
    location_id             INTEGER NOT NULL REFERENCES dim_location(location_id),
    state_id                INTEGER NOT NULL REFERENCES dim_state(state_id),
    crop_id                 INTEGER NOT NULL REFERENCES dim_crop(crop_id),
    crop_name               TEXT,
    crop_year               INTEGER NOT NULL REFERENCES dim_year(crop_year),
    area_ha                 REAL, production_apy_unit REAL, production_price_qtl REAL, n_seasons INTEGER,
    yield_kg_per_ha         REAL,
    msp_effective           REAL,
    gross_value_msp_inr     REAL,                  -- ESTIMATE; not farmer income
    gross_value_msp_per_ha  REAL,
    gross_value_at_2018_msp_inr REAL,           -- volume view: production x 2018-19 MSP
    cpi_deflator_2018_100   REAL,               -- CPI (World Bank FP.CPI.TOTL), crop-year average, 2018-19 = 100
    gross_value_real_2018_inr REAL,             -- gross value @ MSP in constant 2018-19 rupees (CPI-deflated)
    valuation_basis         TEXT,
    is_provisional_year     INTEGER
);
CREATE INDEX ix_dcy ON fact_district_crop_year(crop_id, crop_year);
CREATE INDEX ix_dcy_state ON fact_district_crop_year(state_id, crop_year);

CREATE TABLE fact_state_crop_year (
    state_crop_year_id       INTEGER PRIMARY KEY,
    state_id                 INTEGER NOT NULL REFERENCES dim_state(state_id),
    crop_id                  INTEGER NOT NULL REFERENCES dim_crop(crop_id),
    crop_year                INTEGER NOT NULL REFERENCES dim_year(crop_year),
    area_ha REAL, production_apy_unit REAL, production_price_qtl REAL,
    gross_value_msp_inr REAL, n_districts INTEGER, crop_name TEXT, state_name TEXT,
    yield_kg_per_ha REAL, yield_price_qtl_per_ha REAL, msp_effective REAL, gross_value_msp_per_ha REAL,
    a2fl_per_ha REAL, c2_per_ha REAL, c2_per_qtl REAL, implied_yield_qtl_per_ha REAL,
    has_official_cost INTEGER,
    est_profit_a2fl_per_ha REAL, est_profit_c2_per_ha REAL, est_profit_c2_per_acre REAL,
    msp_minus_c2_per_qtl REAL, est_margin_c2_pct REAL, apy_vs_coc_yield_ratio REAL,
    mandi_awm_price REAL, months_observed REAL, gross_value_mandi_inr REAL, mandi_vs_msp_pct REAL,
    jjas_mm REAL, jjas_dep_pct REAL, jjas_category TEXT, rabi_rain_mm REAL, rabi_rain_dep_pct REAL,
    rainfall_basis TEXT, rain_metric TEXT, season_rain_dep_pct REAL,
    yield_trend_kg_per_ha REAL, yield_anomaly_pct REAL, is_provisional_year INTEGER
);
CREATE INDEX ix_scy ON fact_state_crop_year(state_id, crop_id, crop_year);

CREATE TABLE fact_msp (
    msp_id            INTEGER PRIMARY KEY,
    crop_id           INTEGER REFERENCES dim_crop(crop_id),
    msp_key           TEXT NOT NULL,
    crop_year         INTEGER NOT NULL,
    crop_year_label   TEXT, marketing_season TEXT, season TEXT, variety TEXT,
    msp_base          REAL NOT NULL,
    bonus             REAL,                       -- NULL = bonus not verified
    bonus_verified    INTEGER,
    msp_effective     REAL NOT NULL,
    a2fl_cost         REAL,                       -- CACP projected all-India A2+FL, Rs/qtl
    msp_over_a2fl_pct REAL,
    msp_real_2018     REAL,                       -- msp_effective in constant 2018-19 rupees (CPI)
    source_id TEXT, source_title TEXT, source_url TEXT, verification TEXT, note TEXT,
    UNIQUE (msp_key, crop_year)
);

CREATE TABLE fact_market_price (
    price_id          INTEGER PRIMARY KEY,
    market_id         INTEGER NOT NULL REFERENCES dim_market(market_id),
    crop_id           INTEGER NOT NULL REFERENCES dim_crop(crop_id),
    date_key          INTEGER NOT NULL REFERENCES dim_date(date_key),
    source_dataset    TEXT NOT NULL, granularity TEXT, commodity_raw TEXT, variety TEXT,
    price_form        TEXT, msp_comparable INTEGER,
    arrivals_qtl      REAL,
    min_price REAL, max_price REAL, modal_price REAL,          -- Rs/qtl
    price_spread REAL, price_spread_pct REAL,
    msp_crop_year INTEGER, msp_applicable REAL, modal_vs_msp_pct REAL, modal_below_msp INTEGER,
    msp_price_band TEXT, msp_price_band_order INTEGER,
    dq_flag TEXT
);
CREATE INDEX ix_price_crop_date ON fact_market_price(crop_id, date_key);
CREATE INDEX ix_price_mkt ON fact_market_price(market_id);

CREATE TABLE fact_cost_of_cultivation (
    cost_id INTEGER PRIMARY KEY,
    crop_name TEXT, state_name TEXT, crop_year INTEGER,
    a2fl_per_ha REAL, c2_per_ha REAL, c2_per_qtl REAL, implied_yield_qtl_per_ha REAL,
    crop_year_label TEXT,
    crop_id INTEGER REFERENCES dim_crop(crop_id),
    state_id INTEGER REFERENCES dim_state(state_id),
    source TEXT
);

CREATE TABLE fact_weather_subdivision (
    weather_id INTEGER PRIMARY KEY, subdivision TEXT NOT NULL, year INTEGER NOT NULL,
    JAN REAL, FEB REAL, MAR REAL, APR REAL, MAY REAL, JUN REAL, JUL REAL, AUG REAL, SEP REAL,
    OCT REAL, NOV REAL, DEC REAL,
    jjas_mm REAL, ond_mm REAL, rabi_rain_mm REAL, annual_mm REAL,
    jjas_normal_mm REAL, jjas_dep_pct REAL, jjas_category TEXT,
    rabi_rain_normal_mm REAL, rabi_rain_dep_pct REAL, annual_normal_mm REAL, annual_dep_pct REAL
);

CREATE TABLE fact_weather_state (
    state_weather_id INTEGER PRIMARY KEY, crop_year INTEGER, jjas_mm REAL, rabi_rain_mm REAL, annual_mm REAL,
    jjas_normal_mm REAL, rabi_rain_normal_mm REAL, annual_normal_mm REAL, state_name TEXT,
    n_subdivisions INTEGER, jjas_dep_pct REAL, rabi_rain_dep_pct REAL, annual_dep_pct REAL,
    jjas_category TEXT, rainfall_basis TEXT, state_id INTEGER REFERENCES dim_state(state_id)
);

CREATE TABLE dq_issues (
    issue_id INTEGER PRIMARY KEY, domain TEXT, issue TEXT, action TEXT, n_rows INTEGER, detail TEXT
);
CREATE TABLE dq_coverage (
    domain TEXT, dimension TEXT, member TEXT, metric TEXT, value REAL
);
CREATE TABLE dq_validation (
    check_name TEXT, crop_name TEXT, crop_year INTEGER, dataset_value REAL, official_value REAL,
    unit TEXT, diff_pct REAL, official_source TEXT, status TEXT
);
CREATE TABLE ref_sources (
    source_id TEXT PRIMARY KEY, dataset TEXT, publisher TEXT, coverage TEXT, grain TEXT,
    used_for TEXT, access_route TEXT, url TEXT, reliability_note TEXT
);

-- ---------------------------------------------------------------- analytical views
CREATE VIEW vw_crop_revenue_summary AS
SELECT c.crop_name, c.crop_group, f.crop_year,
       SUM(f.area_ha)                         AS area_ha,
       SUM(f.production_price_qtl)            AS production_price_qtl,
       SUM(f.gross_value_msp_inr) / 1e7       AS gross_value_msp_crore,
       SUM(f.gross_value_msp_inr) / SUM(CASE WHEN f.gross_value_msp_inr IS NOT NULL THEN f.area_ha END)
                                              AS gross_value_msp_per_ha
FROM fact_district_crop_year f JOIN dim_crop c USING (crop_id)
GROUP BY c.crop_name, c.crop_group, f.crop_year;

CREATE VIEW vw_state_economics AS
SELECT s.state_name, s.region, f.crop_name, f.crop_year, f.area_ha, f.yield_kg_per_ha,
       f.gross_value_msp_inr / 1e7 AS gross_value_msp_crore, f.gross_value_msp_per_ha,
       f.c2_per_ha, f.est_profit_c2_per_ha, f.est_profit_a2fl_per_ha, f.est_margin_c2_pct
FROM fact_state_crop_year f JOIN dim_state s USING (state_id);

CREATE VIEW vw_mandi_msp_comparison AS
SELECT p.source_dataset, c.crop_name, p.price_form, d.price_date, m.state_name, m.market_name,
       p.modal_price, p.msp_applicable, p.modal_vs_msp_pct, p.modal_below_msp
FROM fact_market_price p
JOIN dim_crop c USING (crop_id) JOIN dim_market m USING (market_id) JOIN dim_date d USING (date_key)
WHERE p.msp_applicable IS NOT NULL;

CREATE VIEW vw_market_volatility AS
SELECT m.state_name, m.market_name, c.crop_name, p.price_form,
       COUNT(*) AS n_months, AVG(p.modal_price) AS mean_modal,
       MIN(p.modal_price) AS min_modal, MAX(p.modal_price) AS max_modal,
       AVG(p.price_spread_pct) AS avg_intramonth_spread_pct
FROM fact_market_price p JOIN dim_crop c USING (crop_id) JOIN dim_market m USING (market_id)
WHERE p.granularity = 'Monthly' AND p.dq_flag NOT LIKE 'excluded%'
GROUP BY m.state_name, m.market_name, c.crop_name, p.price_form;
