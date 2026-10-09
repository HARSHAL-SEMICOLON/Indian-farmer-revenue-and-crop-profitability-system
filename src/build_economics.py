"""
Crop economics: estimated gross value of output, per-hectare economics, profit (where costs exist),
yield anomalies and rainfall linkage.

TERMINOLOGY (enforced in column names):
  gross_value_msp_inr   = production (in MSP commodity form, qtl) x effective MSP of that crop year.
                          An ESTIMATE of gross crop value at the support price. It is NOT realised price,
                          NOT farmer income (no deduction of costs, no procurement-coverage adjustment,
                          ignores by-products, other enterprises, wages, transfers).
  gross_value_mandi_inr = production x arrival-weighted mandi modal price (Maharashtra 2014-15 only).
  est_profit_*_per_ha   = MSP-valued gross value per ha - DES cost per ha (A2+FL or C2) - only where a
                          DES state x crop x year cost exists (2008-09 .. 2013-14).
"""
import numpy as np
import pandas as pd
from .config import (cpi_deflator_2018, RAW, PROC, CURATED, ACRES_PER_HA, MSP_VALUATION_YEARS, PROVISIONAL_YEARS, RAINFALL_LAST_YEAR)
from .build_prices import msp_crop_year  # noqa: F401  (documented rule, reused in docs/tests)

KG_PER_APY_UNIT = {"Cotton": 170.0, "Jute": 180.0}   # bales -> kg; all others tonnes -> 1000 kg


def main():
    crop = pd.read_csv(PROC / "dim_crop.csv")
    loc = pd.read_csv(PROC / "dim_location.csv")
    st = pd.read_csv(PROC / "dim_state.csv")
    prod = pd.read_csv(PROC / "fact_production.csv")
    msp = pd.read_csv(CURATED / "msp_official_curated.csv")
    coc = pd.read_csv(PROC / "fact_cost_of_cultivation.csv")
    wst = pd.read_csv(PROC / "fact_weather_state.csv")
    price = pd.read_csv(PROC / "fact_market_price.csv", dtype={"variety": str})
    dates = pd.read_csv(PROC / "dim_date.csv", parse_dates=["price_date"])

    prod = prod[prod.dq_flag != "excluded"]
    prod = prod.merge(crop[["crop_id", "crop_name", "msp_key", "primary_season"]], on="crop_id").merge(
        loc[["location_id", "state_id", "state_name"]], on="location_id")

    # ---------------- district x crop x year (all seasons summed) --------------------------------
    g = prod.groupby(["location_id", "state_id", "state_name", "crop_id", "crop_name", "msp_key", "crop_year"],
                     as_index=False, dropna=False).agg(
        area_ha=("area_ha", "sum"), production_apy_unit=("production_apy_unit", "sum"),
        production_price_qtl=("production_price_qtl", "sum"), n_seasons=("season", "nunique"))
    g["kg_per_unit"] = g["crop_name"].map(KG_PER_APY_UNIT).fillna(1000.0)
    g["yield_kg_per_ha"] = g["production_apy_unit"] * g["kg_per_unit"] / g["area_ha"]
    mlook = msp.set_index(["msp_key", "crop_year"])["msp_effective"]
    g["msp_effective"] = [mlook.get((k, y), np.nan) if isinstance(k, str) else np.nan
                          for k, y in zip(g["msp_key"], g["crop_year"])]
    in_window = g["crop_year"].isin(MSP_VALUATION_YEARS)
    g.loc[~in_window, "msp_effective"] = np.nan
    g["gross_value_msp_inr"] = g["production_price_qtl"] * g["msp_effective"]
    g["gross_value_msp_per_ha"] = g["gross_value_msp_inr"] / g["area_ha"]
    msp2018 = msp[msp.crop_year == 2018].set_index("msp_key")["msp_effective"]
    g["gross_value_at_2018_msp_inr"] = np.where(g["gross_value_msp_inr"].notna(),
                                                g["production_price_qtl"] * g["msp_key"].map(msp2018), np.nan)
    # real terms: deflate crop year Y by mean CPI of calendar years Y and Y+1, rebased to 2018-19
    defl = cpi_deflator_2018()
    g["cpi_deflator_2018_100"] = g["crop_year"].map(defl)
    g["gross_value_real_2018_inr"] = g["gross_value_msp_inr"] / g["cpi_deflator_2018_100"] * 100
    g["valuation_basis"] = np.select(
        [g["msp_effective"].notna(), g["msp_key"].isna(), ~in_window],
        ["MSP-valued", "Not valued: no MSP (non-mandated crop)", "Not valued: outside MSP window (2004-2026)"],
        "Not valued: MSP missing for crop-year")
    g["is_provisional_year"] = g["crop_year"].isin(PROVISIONAL_YEARS)
    g = g.drop(columns=["kg_per_unit", "msp_key", "state_name"])
    g.insert(0, "district_crop_year_id", range(1, len(g) + 1))
    g.to_csv(PROC / "fact_district_crop_year.csv", index=False)

    # ---------------- state x crop x year -----------------------------------------------------
    s = g.groupby(["state_id", "crop_id", "crop_year"], as_index=False).agg(
        area_ha=("area_ha", "sum"), production_apy_unit=("production_apy_unit", "sum"),
        production_price_qtl=("production_price_qtl", "sum"),
        gross_value_msp_inr=("gross_value_msp_inr", lambda x: x.sum(min_count=1)),
        n_districts=("location_id", "nunique"))
    s = s.merge(crop[["crop_id", "crop_name", "msp_key"]], on="crop_id").merge(st[["state_id", "state_name"]], on="state_id")
    s["kg_per_unit"] = s["crop_name"].map(KG_PER_APY_UNIT).fillna(1000.0)
    s["yield_kg_per_ha"] = s["production_apy_unit"] * s["kg_per_unit"] / s["area_ha"]
    s["yield_price_qtl_per_ha"] = s["production_price_qtl"] / s["area_ha"]
    s["msp_effective"] = [mlook.get((k, y), np.nan) if (isinstance(k, str) and y in MSP_VALUATION_YEARS) else np.nan
                          for k, y in zip(s["msp_key"], s["crop_year"])]
    s["gross_value_msp_per_ha"] = s["gross_value_msp_inr"] / s["area_ha"]

    # --- cost & profit (only exact state x crop x year matches) ---
    s = s.merge(coc[["state_id", "crop_id", "crop_year", "a2fl_per_ha", "c2_per_ha", "c2_per_qtl",
                     "implied_yield_qtl_per_ha"]], on=["state_id", "crop_id", "crop_year"], how="left")
    has_cost = s["c2_per_ha"].notna() & s["gross_value_msp_per_ha"].notna()
    s["has_official_cost"] = s["c2_per_ha"].notna()
    s["est_profit_a2fl_per_ha"] = np.where(has_cost, s["gross_value_msp_per_ha"] - s["a2fl_per_ha"], np.nan)
    s["est_profit_c2_per_ha"] = np.where(has_cost, s["gross_value_msp_per_ha"] - s["c2_per_ha"], np.nan)
    s["est_profit_c2_per_acre"] = s["est_profit_c2_per_ha"] / ACRES_PER_HA
    s["msp_minus_c2_per_qtl"] = s["msp_effective"] - s["c2_per_qtl"]
    s["est_margin_c2_pct"] = s["est_profit_c2_per_ha"] / s["gross_value_msp_per_ha"] * 100
    s["apy_vs_coc_yield_ratio"] = s["yield_price_qtl_per_ha"] / s["implied_yield_qtl_per_ha"]

    # --- Maharashtra mandi-valued gross value (crop years 2014, 2015) ---
    p = price[(price.source_dataset.str.startswith("MH")) & (~price.dq_flag.str.startswith("excluded")) &
              (price.arrivals_qtl > 0)].merge(dates[["date_key", "price_date"]], on="date_key")
    p = p[~p.price_form.isin(["Milled rice", "Sugarcane (mandi)"])]
    p = p.merge(crop[["crop_id", "crop_name", "primary_season"]], on="crop_id")

    def mkt_year(row):
        y = msp_crop_year(row.crop_name, row.price_date)
        if pd.isna(y):  # non-MSP crops: agricultural year Jul-Jun
            y = row.price_date.year if row.price_date.month >= 7 else row.price_date.year - 1
        return y
    p["mkt_crop_year"] = p.apply(mkt_year, axis=1)
    # require >= 10 of 12 months observed in the marketing year
    cover = p.groupby(["crop_id", "mkt_crop_year"]).price_date.nunique()
    p["wtd"] = p["modal_price"] * p["arrivals_qtl"]
    awm = p.groupby(["crop_id", "mkt_crop_year"]).agg(wtd=("wtd", "sum"), arr=("arrivals_qtl", "sum"))
    awm["mandi_awm_price"] = awm.wtd / awm.arr
    awm["months_observed"] = cover
    awm = awm[awm.months_observed >= 10].reset_index().rename(columns={"mkt_crop_year": "crop_year"})
    mh_id = int(st.loc[st.state_name == "Maharashtra", "state_id"].iloc[0])
    awm["state_id"] = mh_id
    s = s.merge(awm[["state_id", "crop_id", "crop_year", "mandi_awm_price", "months_observed"]],
                on=["state_id", "crop_id", "crop_year"], how="left")
    s["gross_value_mandi_inr"] = s["production_price_qtl"] * s["mandi_awm_price"]
    s["mandi_vs_msp_pct"] = (s["mandi_awm_price"] / s["msp_effective"] - 1) * 100

    # --- yield anomaly (detrended) & rainfall ---
    s = s.merge(wst[["state_id", "crop_year", "jjas_mm", "jjas_dep_pct", "jjas_category", "rabi_rain_mm",
                     "rabi_rain_dep_pct", "rainfall_basis"]], on=["state_id", "crop_year"], how="left")
    season = s["crop_id"].map(crop.set_index("crop_id")["primary_season"])
    s["rain_metric"] = np.where(season == "Rabi", "Rabi rain (Oct-Dec + Jan-Feb next)", "Monsoon (Jun-Sep)")
    s["season_rain_dep_pct"] = np.where(season == "Rabi", s["rabi_rain_dep_pct"], s["jjas_dep_pct"])
    s["yield_trend_kg_per_ha"] = np.nan
    s["yield_anomaly_pct"] = np.nan
    window = s.crop_year.between(1997, RAINFALL_LAST_YEAR)
    for (sid, cid), grp in s[window].groupby(["state_id", "crop_id"]):
        grp = grp[grp.yield_kg_per_ha > 0]
        if len(grp) < 10 or grp.area_ha.mean() < 10000:
            continue
        b, a = np.polyfit(grp.crop_year, grp.yield_kg_per_ha, 1)
        trend = a + b * grp.crop_year
        s.loc[grp.index, "yield_trend_kg_per_ha"] = trend
        s.loc[grp.index, "yield_anomaly_pct"] = (grp.yield_kg_per_ha / trend - 1) * 100

    s["is_provisional_year"] = s["crop_year"].isin(PROVISIONAL_YEARS)
    s = s.drop(columns=["kg_per_unit", "msp_key"])
    s.insert(0, "state_crop_year_id", range(1, len(s) + 1))
    s.to_csv(PROC / "fact_state_crop_year.csv", index=False)
    print({"district_crop_year": len(g), "state_crop_year": len(s),
           "msp_valued_share_district_rows": round(g.valuation_basis.eq("MSP-valued").mean(), 3),
           "profit_rows": int(s.est_profit_c2_per_ha.notna().sum()),
           "mh_mandi_valued_rows": int(s.gross_value_mandi_inr.notna().sum()),
           "anomaly_rows": int(s.yield_anomaly_pct.notna().sum())})


if __name__ == "__main__":
    main()
