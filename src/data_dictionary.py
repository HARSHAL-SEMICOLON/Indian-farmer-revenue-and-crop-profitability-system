"""
Write docs/DATA_DICTIONARY.md from the live database: every table, its grain and row count, and every column
with meaning, unit and an example value. Descriptions live here; anything undescribed is reported so it can't
silently go undocumented.
"""
import pandas as pd

from .config import ROOT, connect_ro

TABLES = {
    "dim_crop": ("Dimension", "one row per crop", "Crop registry: names, groups, APY unit and the factor converting APY production to the MSP/price unit"),
    "dim_state": ("Dimension", "one row per state/UT", "States with region and the IMD subdivisions used for rainfall"),
    "dim_location": ("Dimension", "one row per district", "Districts as reported by DES APY"),
    "dim_year": ("Dimension", "one row per crop year 1990-2026", "Crop (agricultural) years, marketing seasons, data-availability flags, CPI deflator"),
    "dim_market": ("Dimension", "one row per mandi/APMC", "Markets reporting prices"),
    "dim_date": ("Dimension", "one row per price date", "Calendar attributes of mandi price dates"),
    "fact_production": ("Fact", "district x crop x crop year x season", "DES APY area and production, cleaned"),
    "fact_district_crop_year": ("Fact", "district x crop x crop year", "Seasons summed; gross value at MSP, real value and volume value"),
    "fact_state_crop_year": ("Fact", "state x crop x crop year", "State totals with cost of cultivation, estimated profit, mandi valuation, rainfall and yield anomaly"),
    "fact_msp": ("Fact", "crop x crop year", "Official MSP/FRP with bonus, CACP cost, real MSP and source URL"),
    "fact_market_price": ("Fact", "market x crop x date (x variety)", "Mandi prices from AGMARKNET and Maharashtra APMC, with the MSP that applied on the date"),
    "fact_cost_of_cultivation": ("Fact", "state x crop x crop year", "DES Cost of Cultivation Scheme estimates (2008-09 to 2013-14)"),
    "fact_weather_state": ("Fact", "state x year", "Seasonal rainfall per state (mean of its IMD subdivisions)"),
    "fact_weather_subdivision": ("Fact", "IMD subdivision x year", "Monthly and seasonal rainfall as published by IMD"),
    "dq_issues": ("Quality", "one row per issue", "Data problems found and how each was handled"),
    "dq_coverage": ("Quality", "domain x member x metric", "Coverage counts per dataset"),
    "dq_validation": ("Quality", "crop x check", "Cleaned totals compared with independent official estimates"),
    "ref_sources": ("Reference", "one row per dataset", "Source register: publisher, coverage, grain, URL, reliability note"),
}

# column -> (meaning, unit). Table-specific entries use "table.column".
COLS = {
    # keys
    "crop_id": ("Crop key (-> dim_crop)", "ID"), "state_id": ("State key (-> dim_state)", "ID"),
    "location_id": ("District key (-> dim_location)", "ID"), "market_id": ("Market key (-> dim_market)", "ID"),
    "date_key": ("Date key YYYYMMDD (-> dim_date)", "ID"),
    "crop_year": ("Crop (agricultural) year, first calendar year: 2016 = 2016-17", "year"),
    "crop_year_label": ("Crop year as text, e.g. 2016-17", "text"),
    "production_id": ("Row key", "ID"), "district_crop_year_id": ("Row key", "ID"), "state_crop_year_id": ("Row key", "ID"),
    "msp_id": ("Row key", "ID"), "price_id": ("Row key", "ID"), "cost_id": ("Row key", "ID"),
    "state_weather_id": ("Row key", "ID"), "weather_id": ("Row key", "ID"), "issue_id": ("Row key", "ID"),
    # names
    "crop_name": ("Crop name", "text"), "state_name": ("State or UT", "text"), "district_name": ("District", "text"),
    "market_name": ("Mandi / APMC name", "text"),
    # dim_crop
    "apy_name": ("Crop name as written in DES APY", "text"), "crop_group": ("Cereals, Pulses, Oilseeds, Fibres, Cash crops, Horticulture, Spices", "text"),
    "primary_season": ("Main growing season (Kharif / Rabi / Whole year)", "text"),
    "apy_unit": ("Unit APY reports production in (tonnes; milled rice; 170-kg lint bales; 180-kg jute bales)", "text"),
    "dim_crop.price_form": ("Commodity form MSP is defined for (paddy, kapas, whole grain...)", "text"),
    "to_price_qtl_factor": ("Multiply APY production by this to get quintals of the MSP form (rice 10/0.67 = 14.93; cotton bale 1.7/0.34 = 5.0; tonnes x10)", "factor"),
    "msp_key": ("MSP crop name used to join MSP", "text"), "is_msp_crop": ("1 = government announces an MSP/FRP for this crop", "0/1"),
    # dim_state / location / market / date / year
    "region": ("North / South / East / West / Central / North-East", "text"),
    "state_group": ("State with its pre-2000/2014 parent merged (for consistent long trends)", "text"),
    "imd_subdivisions": ("IMD meteorological subdivisions averaged for the state", "text"),
    "district_key": ("state|district natural key", "text"), "first_year": ("First crop year the district reports", "year"),
    "last_year": ("Last crop year the district reports", "year"), "first_seen_in": ("Price dataset where the market first appears", "text"),
    "price_date": ("Price date", "date"), "year": ("Calendar year", "year"), "month": ("Calendar month", "1-12"),
    "month_name": ("Month name", "text"), "year_month": ("YYYY-MM", "text"),
    "agri_year": ("Crop year the date falls in (Jul-Jun)", "year"), "agri_year_label": ("Crop year label", "text"),
    "season_window": ("Kharif window (Jun-Oct) / Rabi window (Nov-Mar) / other", "text"),
    "kharif_marketing_season": ("KMS that sells this crop year's kharif crop (Oct Y - Sep Y+1)", "text"),
    "rabi_marketing_season": ("RMS that sells this crop year's rabi crop (Apr Y+1 - Mar Y+2)", "text"),
    "has_production_data": ("APY production available", "0/1"), "in_msp_valuation_window": ("Crop year inside the official MSP series used for valuation (2004-2026)", "0/1"),
    "is_provisional": ("Provisional year (2019-20)", "0/1"), "is_provisional_year": ("Provisional year (2019-20)", "0/1"),
    "has_cost_data": ("DES cost data exist (2008-2013)", "0/1"), "has_rainfall_data": ("Rainfall data exist (to 2015)", "0/1"),
    "cpi_deflator_2018_100": ("CPI deflator, mean of calendar years Y and Y+1, 2018-19 = 100 (World Bank FP.CPI.TOTL)", "index"),
    "decade": ("5-year bucket", "text"),
    # production / value
    "season": ("APY season (Kharif, Rabi, Whole Year, Summer, Autumn, Winter)", "text"),
    "area_ha": ("Area sown/harvested", "hectares"),
    "production_apy_unit": ("Production in the APY unit (see dim_crop.apy_unit)", "tonnes / bales"),
    "production_price_qtl": ("Production converted to the MSP commodity form", "quintals"),
    "yield_apy_unit_per_ha": ("Production per hectare in APY unit", "APY unit/ha"),
    "yield_kg_per_ha": ("Yield (cotton: kg lint/ha; rice: kg milled rice/ha)", "kg/ha"),
    "yield_price_qtl_per_ha": ("Yield in the MSP commodity form", "qtl/ha"),
    "n_seasons": ("Seasons summed into the row", "count"), "n_districts": ("Districts summed into the row", "count"),
    "msp_effective": ("MSP + verified bonus for the crop year", "Rs/qtl"),
    "gross_value_msp_inr": ("Estimated gross value = production_price_qtl x msp_effective. NOT farmer income", "Rs"),
    "gross_value_msp_per_ha": ("Gross value at MSP per hectare", "Rs/ha"),
    "gross_value_at_2018_msp_inr": ("Volume measure: production valued at constant 2018-19 MSP", "Rs (2018-19 MSP)"),
    "gross_value_real_2018_inr": ("Real value: gross value deflated by CPI to 2018-19 rupees", "Rs (2018-19)"),
    "valuation_basis": ("Why a row is or isn't valued (no MSP / outside window)", "text"),
    # cost & profit
    "a2fl_per_ha": ("DES cost A2+FL: paid-out costs + imputed family labour", "Rs/ha"),
    "c2_per_ha": ("DES cost C2: comprehensive, incl. imputed rent and interest on owned land/capital", "Rs/ha"),
    "c2_per_qtl": ("C2 cost per quintal of main product", "Rs/qtl"),
    "implied_yield_qtl_per_ha": ("Yield implied by DES cost survey (C2/ha / C2/qtl)", "qtl/ha"),
    "has_official_cost": ("DES cost exists for this state x crop x year", "0/1"),
    "est_profit_a2fl_per_ha": ("Gross value at MSP per ha - A2+FL per ha", "Rs/ha"),
    "est_profit_c2_per_ha": ("Gross value at MSP per ha - C2 per ha", "Rs/ha"),
    "est_profit_c2_per_acre": ("Estimated profit over C2 per acre", "Rs/acre"),
    "msp_minus_c2_per_qtl": ("MSP - C2 cost per quintal", "Rs/qtl"), "est_margin_c2_pct": ("Profit over C2 / C2 cost", "%"),
    "apy_vs_coc_yield_ratio": ("APY yield / cost-survey yield (bias check)", "ratio"),
    "mandi_awm_price": ("Arrival-weighted mandi modal price (Maharashtra 2014-15)", "Rs/qtl"),
    "months_observed": ("Months of mandi data behind mandi_awm_price", "count"),
    "gross_value_mandi_inr": ("Production x mandi price (Maharashtra 2014-15 only)", "Rs"),
    "mandi_vs_msp_pct": ("Mandi price vs MSP", "%"),
    "source": ("Source dataset", "text"),
    # weather
    "jjas_mm": ("Monsoon (Jun-Sep) rainfall", "mm"), "rabi_rain_mm": ("Rabi-season rainfall (Oct-Dec + Jan-Feb next year)", "mm"),
    "annual_mm": ("Annual rainfall", "mm"), "ond_mm": ("Oct-Dec rainfall", "mm"),
    "jjas_normal_mm": ("1951-2000 mean monsoon rainfall of this series", "mm"),
    "rabi_rain_normal_mm": ("1951-2000 mean rabi rainfall", "mm"), "annual_normal_mm": ("1951-2000 mean annual rainfall", "mm"),
    "jjas_dep_pct": ("Monsoon departure from normal", "%"), "rabi_rain_dep_pct": ("Rabi rainfall departure from normal", "%"),
    "annual_dep_pct": ("Annual departure from normal", "%"),
    "jjas_category": ("IMD category: Large excess / Excess / Normal / Deficient / Large deficient", "text"),
    "rainfall_basis": ("How state rainfall was built (subdivision mean)", "text"),
    "n_subdivisions": ("IMD subdivisions averaged", "count"), "subdivision": ("IMD meteorological subdivision", "text"),
    "rain_metric": ("Rain metric matched to the crop's season", "text"),
    "season_rain_dep_pct": ("Departure of the season-matched rainfall", "%"),
    "yield_trend_kg_per_ha": ("Linear-trend yield for the state x crop", "kg/ha"),
    "yield_anomaly_pct": ("Yield vs its own linear trend (detrended)", "%"),
    # MSP
    "marketing_season": ("Marketing season the MSP applies to (KMS / RMS)", "text"), "variety": ("Variety / grade", "text"),
    "msp_base": ("Announced MSP / FRP", "Rs/qtl"), "bonus": ("State/central bonus over MSP (NULL = not verified)", "Rs/qtl"),
    "bonus_verified": ("Bonus confirmed in an official source", "0/1"),
    "a2fl_cost": ("CACP projected all-India A2+FL cost", "Rs/qtl"), "msp_over_a2fl_pct": ("MSP margin over A2+FL", "%"),
    "msp_real_2018": ("MSP in constant 2018-19 rupees (msp_effective / CPI deflator x 100)", "Rs/qtl (2018-19)"),
    "source_id": ("Source key (see ref_sources / curated source list)", "text"), "source_title": ("Source document", "text"),
    "source_url": ("URL of the official release", "url"), "verification": ("official / secondary", "text"), "note": ("Note", "text"),
    # prices
    "source_dataset": ("Price dataset (MH APMC monthly 2014-16 / AGMARKNET 30-Sep-2024 / AGMARKNET Jul-Sep 2026)", "text"),
    "granularity": ("Monthly or Daily", "text"), "commodity_raw": ("Commodity label as published", "text"),
    "fact_market_price.price_form": ("Commodity form of the quote (paddy, milled rice, kapas, dal...)", "text"),
    "msp_comparable": ("Form matches the MSP form (only these are compared with MSP)", "0/1"),
    "arrivals_qtl": ("Market arrivals (Maharashtra only)", "quintals"),
    "min_price": ("Minimum price", "Rs/qtl"), "max_price": ("Maximum price", "Rs/qtl"), "modal_price": ("Modal (most common) price", "Rs/qtl"),
    "price_spread": ("max - min", "Rs/qtl"), "price_spread_pct": ("(max - min) / modal", "%"),
    "msp_crop_year": ("Crop year whose MSP applies on the price date (marketing-season rule)", "year"),
    "msp_applicable": ("MSP in force on the price date", "Rs/qtl"), "modal_vs_msp_pct": ("Modal price vs MSP", "%"),
    "modal_below_msp": ("Modal price < MSP", "0/1"), "msp_price_band": ("Distance from MSP bucket (>20% below ... >10% above)", "text"),
    "msp_price_band_order": ("Sort order of msp_price_band", "1-5"),
    "dq_flag": ("ok / flag: ... / excluded: ... (excluded rows are left out of analysis)", "text"),
    # monthly rainfall
    **{m: (f"{m.title()} rainfall", "mm") for m in ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]},
    # dq / ref
    "domain": ("Area of the data", "text"), "issue": ("Problem found", "text"), "action": ("How it was handled", "text"),
    "n_rows": ("Rows affected", "count"), "detail": ("Detail", "text"), "dimension": ("Coverage dimension", "text"),
    "member": ("Coverage member", "text"), "metric": ("Coverage metric", "text"), "value": ("Metric value", "number"),
    "check_name": ("Validation check", "text"), "dataset_value": ("Value from this project", "unit column"),
    "official_value": ("Independent official value", "unit column"), "unit": ("Unit of the two values", "text"),
    "diff_pct": ("dataset vs official", "%"), "official_source": ("Official source and URL", "text"),
    "status": ("consistent (within 10%) / divergent", "text"),
    "dataset": ("Dataset name", "text"), "publisher": ("Publisher", "text"), "coverage": ("Time / space coverage", "text"),
    "grain": ("Row grain", "text"), "used_for": ("Used for", "text"), "access_route": ("How it was obtained", "text"),
    "url": ("URL", "url"), "reliability_note": ("Known limitations", "text"),
}


def main():
    con = connect_ro()
    L = ["# Data dictionary", "",
         "Generated from the SQLite database by `src/data_dictionary.py`. Prices are Rs per quintal (1 quintal = 100 kg) unless stated.",
         "*Gross value* columns are estimates (production x price) and **not farmer income**.", "",
         "## Tables", "", "| Table | Type | Grain | Rows | Contents |", "|---|---|---|---|---|"]
    missing = []
    for t, (kind, grain, desc) in TABLES.items():
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        L.append(f"| [`{t}`](#{t}) | {kind} | {grain} | {n:,} | {desc} |")
    for t, (kind, grain, desc) in TABLES.items():
        df = pd.read_sql_query(f"SELECT * FROM {t} LIMIT 200", con)
        L += ["", f"## {t}", "", f"{desc}. Grain: {grain}.", "", "| Column | Meaning | Unit | Example |", "|---|---|---|---|"]
        for c in df.columns:
            meaning, unit = COLS.get(f"{t}.{c}", COLS.get(c, (None, None)))
            if meaning is None:
                missing.append(f"{t}.{c}")
                meaning, unit = "", ""
            ex = df[c].dropna()
            ex = "" if ex.empty else str(ex.iloc[0])
            ex = (ex[:40] + "…") if len(ex) > 40 else ex
            L.append(f"| `{c}` | {meaning} | {unit} | {ex.replace('|', '/')} |")
    con.close()
    (ROOT / "docs" / "DATA_DICTIONARY.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"data dictionary: {len(TABLES)} tables; undocumented columns: {missing or 'none'}")


if __name__ == "__main__":
    main()
