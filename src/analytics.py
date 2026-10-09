"""
Answer the 10 business questions. SQL-first (sql/analysis/*.sql); Python for statistics.
Outputs: outputs/results/*.csv  and  outputs/results/findings.md
"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .config import connect_ro, RESULTS, SQL_DIR

SQL_DIR = SQL_DIR / "analysis"
RECENT = (2014, 2018)


def q(con, sql):
    return pd.read_sql_query(sql, con)


def cagr(a, b, years):
    return ((b / a) ** (1 / years) - 1) * 100 if a and a > 0 and b > 0 else np.nan


def main():
    con = connect_ro()
    out = {}
    for f in sorted(SQL_DIR.glob("*.sql")):
        out[f.stem] = q(con, f.read_text(encoding="utf-8"))

    dcy = q(con, """SELECT f.*, c.crop_group, c.msp_key FROM fact_district_crop_year f JOIN dim_crop c USING(crop_id)""")
    scy = q(con, "SELECT * FROM fact_state_crop_year")
    msp = q(con, "SELECT * FROM fact_msp")
    price = q(con, """SELECT p.*, c.crop_name, c.msp_key, m.state_name, m.market_name, d.price_date, d.year_month
                      FROM fact_market_price p JOIN dim_crop c USING(crop_id) JOIN dim_market m USING(market_id)
                      JOIN dim_date d USING(date_key)""")
    price = price[~price.dq_flag.str.startswith("excluded")]

    # ---------- Q4: yield vs revenue -------------------------------------------------------------
    # (a) cross-district: within a crop & year MSP is uniform, so value/ha differences are yield differences.
    rec = dcy[dcy.crop_year.between(*RECENT) & dcy.gross_value_msp_inr.notna() & (dcy.area_ha >= 1000)]
    rows = []
    for crop, g in rec.groupby("crop_name"):
        lo, hi = g.yield_kg_per_ha.quantile([0.25, 0.75])
        bot = g[g.yield_kg_per_ha <= lo]
        top = g[g.yield_kg_per_ha >= hi]
        rows.append(dict(crop_name=crop, district_years=len(g),
                         bottom_quartile_yield_kg_ha=round(bot.yield_kg_per_ha.median()),
                         top_quartile_yield_kg_ha=round(top.yield_kg_per_ha.median()),
                         bottom_quartile_value_per_ha=round(bot.gross_value_msp_per_ha.median()),
                         top_quartile_value_per_ha=round(top.gross_value_msp_per_ha.median()),
                         value_gap_per_ha=round(top.gross_value_msp_per_ha.median() - bot.gross_value_msp_per_ha.median()),
                         value_per_ha_ratio=round(top.gross_value_msp_per_ha.median() / bot.gross_value_msp_per_ha.median(), 2)))
    out["q04a_yield_quartile_value_gap"] = pd.DataFrame(rows).sort_values("value_gap_per_ha", ascending=False)

    # (b) growth decomposition 2004-06 avg -> 2016-18 avg: dln(value) = dln(area) + dln(yield) + dln(MSP)
    nat = dcy[dcy.gross_value_msp_inr.notna()].groupby(["crop_name", "crop_year"]).agg(
        area=("area_ha", "sum"), qty=("production_price_qtl", "sum"), value=("gross_value_msp_inr", "sum")).reset_index()
    nat["msp"] = nat.value / nat.qty
    nat["yield"] = nat.qty / nat.area
    dec = []
    for crop, g in nat.groupby("crop_name"):
        a = g[g.crop_year.between(2004, 2006)][["area", "yield", "msp", "value", "qty"]].mean()
        b = g[g.crop_year.between(2016, 2018)][["area", "yield", "msp", "value", "qty"]].mean()
        if g.crop_year.between(2004, 2006).sum() < 3 or g.crop_year.between(2016, 2018).sum() < 3:
            continue
        tot = np.log(b.value / a.value)
        dec.append(dict(crop_name=crop,
                        value_growth_pct=round((b.value / a.value - 1) * 100, 1),
                        area_contribution_pct=round(np.log(b.area / a.area) / tot * 100, 1),
                        yield_contribution_pct=round(np.log(b["yield"] / a["yield"]) / tot * 100, 1),
                        price_msp_contribution_pct=round(np.log(b.msp / a.msp) / tot * 100, 1),
                        production_cagr_pct=round(cagr(a.qty, b.qty, 12), 2),
                        yield_cagr_pct=round(cagr(a["yield"], b["yield"], 12), 2),
                        area_cagr_pct=round(cagr(a.area, b.area, 12), 2),
                        msp_cagr_pct=round(cagr(a.msp, b.msp, 12), 2)))
    out["q04b_value_growth_decomposition"] = pd.DataFrame(dec).sort_values("value_growth_pct", ascending=False)

    # ---------- Q5: price differences across markets --------------------------------------------
    snap = price[price.source_dataset == "AGMARKNET daily snapshot 30-Sep-2024"]
    disp = []
    for (crop, form), g in snap.groupby(["crop_name", "price_form"]):
        if len(g) < 10:
            continue
        v = g.modal_price
        disp.append(dict(crop_name=crop, price_form=form, n_markets=len(g), n_states=g.state_name.nunique(),
                         min_modal=v.min(), p25=v.quantile(.25), median=v.median(), p75=v.quantile(.75),
                         max_modal=v.max(), cv_pct=round(v.std() / v.mean() * 100, 1),
                         p90_p10_ratio=round(v.quantile(.9) / v.quantile(.1), 2),
                         cheapest_state=g.groupby("state_name").modal_price.median().idxmin(),
                         dearest_state=g.groupby("state_name").modal_price.median().idxmax()))
    out["q05a_cross_market_dispersion_2024"] = pd.DataFrame(disp).sort_values("cv_pct", ascending=False)
    st_med = snap.groupby(["crop_name", "price_form", "state_name"]).modal_price.agg(["median", "count"]).reset_index()
    out["q05b_state_median_price_2024"] = st_med[st_med["count"] >= 3]
    mh = price[price.source_dataset.str.startswith("MH")]
    mm = mh.groupby(["crop_name", "price_form", "year_month"]).modal_price.agg(
        lambda x: x.std() / x.mean() * 100 if len(x) >= 5 else np.nan).groupby(["crop_name", "price_form"]).median()
    out["q05c_mh_cross_apmc_cv_by_month"] = mm.rename("median_monthly_cross_apmc_cv_pct").round(1).reset_index() \
        .sort_values("median_monthly_cross_apmc_cv_pct", ascending=False)

    # ---------- Q6b: MH monthly MSP gap ---------------------------------------------------------
    mhc = mh[mh.msp_applicable.notna() & (mh.arrivals_qtl > 0)].copy()
    mhc["w"] = mhc.arrivals_qtl
    g = mhc.groupby(["crop_name", "year_month"]).apply(
        lambda x: pd.Series({"awm_modal": np.average(x.modal_price, weights=x.w), "msp": x.msp_applicable.mean(),
                             "arrivals_qtl": x.w.sum(),
                             "share_arrivals_below_msp_pct": 100 * x.loc[x.modal_below_msp == 1, "w"].sum() / x.w.sum()}))
    g = g.reset_index()
    g["awm_vs_msp_pct"] = (g.awm_modal / g.msp - 1) * 100
    out["q06b_mh_monthly_msp_gap"] = g.round(1)

    # ---------- Q7: rainfall vs yield (association only) -----------------------------------------
    r = scy[scy.yield_anomaly_pct.notna() & scy.season_rain_dep_pct.notna()]
    rr = []
    for crop, g in r.groupby("crop_name"):
        if len(g) < 30:
            continue
        pr, pp = stats.pearsonr(g.season_rain_dep_pct, g.yield_anomaly_pct)
        sr, sp = stats.spearmanr(g.season_rain_dep_pct, g.yield_anomaly_pct)
        slope = np.polyfit(g.season_rain_dep_pct, g.yield_anomaly_pct, 1)[0]
        defi = g[g.season_rain_dep_pct <= -20].yield_anomaly_pct.mean()
        norm = g[g.season_rain_dep_pct.between(-19.99, 19.99)].yield_anomaly_pct.mean()
        rr.append(dict(crop_name=crop, rain_metric=g.rain_metric.iloc[0], n_state_years=len(g),
                       n_states=g.state_id.nunique(), pearson_r=round(pr, 3), pearson_p=round(pp, 4),
                       spearman_rho=round(sr, 3), spearman_p=round(sp, 4),
                       yield_anomaly_pp_per_10pct_rain=round(slope * 10, 2),
                       mean_anomaly_when_deficient_pct=round(defi, 1), mean_anomaly_when_normal_pct=round(norm, 1),
                       significant_5pct="yes" if pp < 0.05 else "no"))
    out["q07a_rain_yield_association"] = pd.DataFrame(rr).sort_values("pearson_r", ascending=False)
    cat = r.copy()
    cat["rain_band"] = pd.cut(cat.season_rain_dep_pct, [-100, -40, -20, 0, 20, 40, 1000],
                              labels=["<= -40%", "-40 to -20%", "-20 to 0%", "0 to +20%", "+20 to +40%", "> +40%"])
    out["q07b_yield_anomaly_by_rain_band"] = cat.groupby(["crop_name", "rain_band"], observed=True).yield_anomaly_pct.agg(
        ["mean", "median", "count"]).round(1).reset_index()
    st_r = []
    for (crop, state), g in r.groupby(["crop_name", "state_name"]):
        if len(g) >= 12:
            pr, pp = stats.pearsonr(g.season_rain_dep_pct, g.yield_anomaly_pct)
            st_r.append(dict(crop_name=crop, state_name=state, n_years=len(g), pearson_r=round(pr, 3),
                             p_value=round(pp, 4), avg_area_ha=round(g.area_ha.mean())))
    out["q07c_rain_yield_by_state"] = pd.DataFrame(st_r).sort_values("pearson_r", ascending=False)

    # ---------- Q8: high production, low profitability ------------------------------------------
    q1 = out["q01_top_revenue_crops"].copy()
    q1["value_rank"] = q1.avg_annual_gross_value_crore.rank(ascending=False)
    q1["value_per_ha_rank"] = q1.gross_value_per_ha.rank(ascending=False)
    q2 = out["q02_profit_per_ha"][["crop_name", "est_profit_c2_per_ha", "est_profit_a2fl_per_ha", "pct_state_years_c2_loss"]]
    q8 = q1.merge(q2, on="crop_name", how="left")
    med_area = q8.avg_area_mha.median()
    med_vph = q8.gross_value_per_ha.median()
    q8["quadrant"] = np.select(
        [(q8.avg_area_mha >= med_area) & (q8.gross_value_per_ha < med_vph),
         (q8.avg_area_mha >= med_area) & (q8.gross_value_per_ha >= med_vph),
         (q8.avg_area_mha < med_area) & (q8.gross_value_per_ha >= med_vph)],
        ["Large footprint, low value/ha", "Large footprint, high value/ha", "Small footprint, high value/ha"],
        "Small footprint, low value/ha")
    out["q08a_footprint_vs_value_per_ha"] = q8.sort_values("avg_area_mha", ascending=False)
    hp = scy[scy.est_profit_c2_per_ha.notna()].copy()
    hp["prod_rank_in_crop_year"] = hp.groupby(["crop_name", "crop_year"]).production_apy_unit.rank(ascending=False)
    out["q08b_major_producers_with_c2_loss"] = hp[(hp.prod_rank_in_crop_year <= 2) & (hp.est_profit_c2_per_ha < 0)][
        ["crop_name", "state_name", "crop_year", "production_apy_unit", "yield_kg_per_ha", "gross_value_msp_per_ha",
         "c2_per_ha", "est_profit_c2_per_ha", "est_profit_a2fl_per_ha"]].round(0).sort_values(["crop_name", "crop_year"])

    # ---------- Q9b: nominal vs constant-MSP (volume) --------------------------------------------
    base = msp[msp.crop_year == 2018].set_index("msp_key").msp_effective
    v = dcy[dcy.gross_value_msp_inr.notna()].copy()
    v["value_at_2018_msp"] = v.production_price_qtl * v.msp_key.map(base)
    t = v.groupby("crop_year").agg(nominal=("gross_value_msp_inr", "sum"), constant_2018_msp=("value_at_2018_msp", "sum"),
                                   real_cpi_2018=("gross_value_real_2018_inr", "sum"))
    t = (t / 1e7).round(0)
    t["nominal_index_2004_100"] = (t.nominal / t.nominal.iloc[0] * 100).round(1)
    t["volume_index_2004_100"] = (t.constant_2018_msp / t.constant_2018_msp.iloc[0] * 100).round(1)
    t["real_index_2004_100"] = (t.real_cpi_2018 / t.real_cpi_2018.iloc[0] * 100).round(1)
    out["q09b_nominal_vs_volume"] = t.reset_index()
    out["q09c_crop_value_trend"] = (nat.pivot_table(index="crop_year", columns="crop_name", values="value") / 1e7).round(0).reset_index()

    # ---------- Q10: markets with large price variation ------------------------------------------
    mv = []
    for (st, mk, crop, form), g in mh.groupby(["state_name", "market_name", "crop_name", "price_form"]):
        if g.year_month.nunique() < 18:
            continue
        v_ = g.sort_values("price_date").modal_price
        mv.append(dict(state_name=st, market_name=mk, crop_name=crop, price_form=form, months=len(v_),
                       mean_modal=round(v_.mean()), cv_pct=round(v_.std() / v_.mean() * 100, 1),
                       max_min_ratio=round(v_.max() / v_.min(), 2),
                       median_intramonth_spread_pct=round(g.price_spread_pct.median(), 1),
                       mean_abs_mom_change_pct=round((v_.pct_change().abs() * 100).mean(), 1)))
    mv = pd.DataFrame(mv)
    out["q10a_market_volatility_mh"] = mv.sort_values("cv_pct", ascending=False)
    out["q10b_volatility_by_crop_mh"] = mv.groupby("crop_name").agg(
        markets=("market_name", "nunique"), median_cv_pct=("cv_pct", "median"),
        median_intramonth_spread_pct=("median_intramonth_spread_pct", "median")).round(1).reset_index() \
        .sort_values("median_cv_pct", ascending=False)
    sp = snap[snap.price_spread_pct.notna()].groupby(["state_name", "market_name"]).agg(
        n_commodities=("crop_name", "nunique"), median_spread_pct=("price_spread_pct", "median")).reset_index()
    out["q10c_snapshot_intraday_spread_2024"] = sp[sp.n_commodities >= 3].sort_values("median_spread_pct", ascending=False)

    # ---------- Recent markets: AGMARKNET daily Jul-Sep 2026 -------------------------------------
    r26 = price[price.source_dataset == "AGMARKNET daily Jul-Sep 2026"].copy()
    r26["price_date"] = pd.to_datetime(r26["price_date"])
    cmp26 = r26[r26.msp_applicable.notna()]
    out["q11a_msp_gap_2026"] = cmp26.groupby(["crop_name", "price_form"]).agg(
        quotes=("modal_price", "size"), markets=("market_id", "nunique"), states=("state_name", "nunique"),
        msp=("msp_applicable", "first"), median_modal=("modal_price", "median"),
        pct_quotes_below_msp=("modal_below_msp", lambda x: 100 * x.mean()),
        avg_modal_vs_msp_pct=("modal_vs_msp_pct", "mean")).round(1).reset_index() \
        .query("quotes >= 30").sort_values("pct_quotes_below_msp", ascending=False)
    cmp26 = cmp26.assign(month=cmp26.price_date.dt.strftime("%Y-%m"))
    out["q11b_msp_gap_by_month_2026"] = cmp26.groupby(["crop_name", "month"]).agg(
        quotes=("modal_price", "size"), pct_below_msp=("modal_below_msp", lambda x: 100 * x.mean()),
        median_modal=("modal_price", "median"), msp=("msp_applicable", "first")).round(1).reset_index()
    rows = []
    for (crop, form), g in r26.groupby(["crop_name", "price_form"]):
        daily = g.groupby("price_date").modal_price.agg(lambda x: x.std() / x.mean() * 100 if len(x) >= 10 else np.nan).dropna()
        if len(daily) < 10:
            continue
        stm = g.groupby("state_name").modal_price.median()
        stm = stm[g.groupby("state_name").size() >= 20]
        rows.append(dict(crop_name=crop, price_form=form, quotes=len(g), markets=g.market_id.nunique(),
                         median_daily_cross_market_cv_pct=round(daily.median(), 1),
                         p25=g.modal_price.quantile(.25), median=g.modal_price.median(), p75=g.modal_price.quantile(.75),
                         cheapest_state=stm.idxmin() if len(stm) else None, cheapest_state_median=stm.min() if len(stm) else None,
                         dearest_state=stm.idxmax() if len(stm) else None, dearest_state_median=stm.max() if len(stm) else None))
    out["q11c_dispersion_2026"] = pd.DataFrame(rows).sort_values("median_daily_cross_market_cv_pct", ascending=False)
    mv26 = []
    for (st, mk, crop, form), g in r26.groupby(["state_name", "market_name", "crop_name", "price_form"]):
        if g.price_date.nunique() < 30:
            continue
        v_ = g.sort_values("price_date").modal_price
        mv26.append(dict(state_name=st, market_name=mk, crop_name=crop, price_form=form, trading_days=g.price_date.nunique(),
                         mean_modal=round(v_.mean()), cv_pct=round(v_.std() / v_.mean() * 100, 1),
                         max_min_ratio=round(v_.max() / v_.min(), 2)))
    mv26 = pd.DataFrame(mv26)
    out["q11d_market_volatility_2026"] = mv26.sort_values("cv_pct", ascending=False)
    out["q11e_volatility_by_crop_2026"] = mv26.groupby("crop_name").agg(markets=("market_name", "nunique"),
        median_cv_pct=("cv_pct", "median")).round(1).reset_index().sort_values("median_cv_pct", ascending=False)
    top = ["Wheat", "Rice", "Maize", "Soyabean", "Groundnut", "Gram", "Onion", "Potato"]
    out["q11f_daily_median_price_2026"] = r26[r26.crop_name.isin(top) & r26.msp_comparable.astype(bool) | r26.crop_name.isin(["Onion", "Potato"])] \
        .groupby(["crop_name", "price_date"]).agg(median_modal=("modal_price", "median"), quotes=("modal_price", "size"),
                                                 msp=("msp_applicable", "first")).reset_index()

    # 2026 season outlook: Jul-Sep 2026 prices vs the MSP announced for the NEXT marketing season
    # (kharif crop year 2026 = KMS 2026-27 from Oct-2026; rabi crop year 2026 = RMS 2027-28 from Apr-2027).
    nxt = msp[msp.crop_year == 2026][["msp_key", "msp_effective", "a2fl_cost", "source_id"]] \
        .rename(columns={"msp_effective": "msp_next", "a2fl_cost": "a2fl_cost_next", "source_id": "msp_next_source"})
    o26 = cmp26.merge(nxt, on="msp_key", how="inner")
    o26["below_next"] = o26.modal_price < o26.msp_next
    out["q11g_season_2026_outlook"] = o26.groupby(["crop_name", "price_form"]).agg(
        quotes=("modal_price", "size"), markets=("market_id", "nunique"),
        msp_current=("msp_applicable", "first"), msp_next=("msp_next", "first"),
        a2fl_cost_next=("a2fl_cost_next", "first"), median_modal=("modal_price", "median"),
        pct_below_current_msp=("modal_below_msp", lambda x: 100 * x.mean()),
        pct_below_next_msp=("below_next", lambda x: 100 * x.mean()),
        msp_next_source=("msp_next_source", "first")).reset_index().query("quotes >= 30")
    g_ = out["q11g_season_2026_outlook"]
    g_["msp_hike_pct"] = (g_.msp_next / g_.msp_current - 1) * 100
    g_["median_modal_vs_next_msp_pct"] = (g_.median_modal / g_.msp_next - 1) * 100
    out["q11g_season_2026_outlook"] = g_.round(1).sort_values("pct_below_next_msp", ascending=False)
    out["q11h_msp_2026_27_vs_cost"] = msp[msp.crop_year == 2026][["msp_key", "season", "crop_year_label", "msp_effective",
        "a2fl_cost", "msp_over_a2fl_pct", "source_id"]].merge(
        msp[msp.crop_year == 2025][["msp_key", "msp_effective"]].rename(columns={"msp_effective": "msp_prev"}), on="msp_key") \
        .assign(hike_pct=lambda d: (d.msp_effective / d.msp_prev - 1) * 100).round(1).sort_values("hike_pct", ascending=False)

    # ---------- Did MSP rise after inflation? (real MSP, constant 2018-19 Rs via CPI) -----------
    rm = msp[msp.msp_real_2018.notna()]
    rows = []
    for k, g in rm.groupby("msp_key"):
        g = g.set_index("crop_year")
        if 2004 not in g.index or 2024 not in g.index:
            continue
        a, b = g.loc[2004], g.loc[2024]
        rows.append(dict(msp_key=k, season=a.season, msp_2004=a.msp_effective, msp_2024=b.msp_effective,
                         nominal_growth_pct=(b.msp_effective / a.msp_effective - 1) * 100,
                         real_msp_2004=a.msp_real_2018, real_msp_2024=b.msp_real_2018,
                         real_growth_pct=(b.msp_real_2018 / a.msp_real_2018 - 1) * 100,
                         real_cagr_pct=((b.msp_real_2018 / a.msp_real_2018) ** (1 / 20) - 1) * 100))
    out["q09c_real_msp_by_crop"] = pd.DataFrame(rows).round(1).sort_values("real_growth_pct", ascending=False)
    out["q09d_real_msp_series"] = rm[["msp_key", "crop_year", "crop_year_label", "msp_effective", "msp_real_2018"]].round(1) \
        .sort_values(["msp_key", "crop_year"])

    # ---------- MSP vs CACP cost ------------------------------------------------------------------
    out["msp_vs_cacp_cost"] = msp[msp.a2fl_cost.notna()][["msp_key", "crop_year_label", "msp_effective", "a2fl_cost",
                                                          "msp_over_a2fl_pct"]].round(1)

    for k, df in out.items():
        df.to_csv(RESULTS / f"{k}.csv", index=False)
    write_findings(out)
    con.close()
    print("analytics outputs:", len(out))
    return out


def write_findings(o):
    q1, q2, q3, q4b = o["q01_top_revenue_crops"], o["q02_profit_per_ha"], o["q03_state_economics"], o["q04b_value_growth_decomposition"]
    q6, q7, q9, q10 = o["q06_mandi_vs_msp"], o["q07a_rain_yield_association"], o["q09b_nominal_vs_volume"], o["q10b_volatility_by_crop_mh"]
    L = ["# Key findings (auto-generated by src/analytics.py)", "",
         "All 'gross value' figures are **estimated gross value of output at MSP** (production x MSP), nominal Rs. "
         "They are not realised prices and **not farmer income**. Profit figures exist only where DES cost data exist "
         "(10 crops, 2008-09..2013-14). Rainfall findings are associations, not causal effects.", ""]
    L.append("## Q1 Highest estimated gross value (avg/yr, 2014-15..2018-19)")
    for _, r in q1.head(5).iterrows():
        L.append(f"- {r.crop_name}: Rs {r.avg_annual_gross_value_crore:,.0f} cr/yr ({r.share_of_msp_valued_pct}% of MSP-valued output)")
    L.append("\n## Q2 Estimated profit per ha over C2 (DES-surveyed states, 2008-09..2013-14)")
    for _, r in q2.iterrows():
        L.append(f"- {r.crop_name}: Rs {r.est_profit_c2_per_ha:,.0f}/ha (Rs {r.est_profit_c2_per_acre:,.0f}/acre); "
                 f"over A2+FL Rs {r.est_profit_a2fl_per_ha:,.0f}/ha; C2 loss in {r.pct_state_years_c2_loss:.0f}% of state-years")
    L.append("\n## Q3 Highest gross value per ha by state (2014-15..2018-19)")
    for _, r in q3.head(5).iterrows():
        L.append(f"- {r.state_name}: Rs {r.gross_value_per_ha:,.0f}/ha")
    L.append("\n## Q4 Value growth decomposition 2004-06 -> 2016-18 (share of log growth)")
    for _, r in q4b.head(6).iterrows():
        L.append(f"- {r.crop_name}: +{r.value_growth_pct}% value; area {r.area_contribution_pct}%, yield {r.yield_contribution_pct}%, MSP {r.price_msp_contribution_pct}%")
    L.append("\n## Q6 Share of mandi quotes below MSP (AGMARKNET daily, 21-Jul to 24-Sep-2026)")
    s = o["q11a_msp_gap_2026"]
    for _, r in s.head(6).iterrows():
        L.append(f"- {r.crop_name} ({r.price_form}): {r.pct_quotes_below_msp}% below MSP, avg modal {r.avg_modal_vs_msp_pct:+.1f}% vs MSP")
    L.append("\n## 2026 season: Jul-Sep 2026 prices vs the newly announced MSP (KMS 2026-27 / RMS 2027-28)")
    g = o["q11g_season_2026_outlook"]
    for _, r in g.head(6).iterrows():
        L.append(f"- {r.crop_name}: MSP {r.msp_current:,.0f} -> {r.msp_next:,.0f} (+{r.msp_hike_pct}%); "
                 f"{r.pct_below_next_msp}% of current quotes below the new MSP (vs {r.pct_below_current_msp}% below the current one)")
    L.append("\n## Q7 Rainfall departure vs detrended yield anomaly (pooled state-years, 1997-2015)")
    for _, r in q7.iterrows():
        L.append(f"- {r.crop_name}: r = {r.pearson_r} (p={r.pearson_p}), {r.yield_anomaly_pp_per_10pct_rain:+} pp yield per +10% rain")
    L.append("\n## Q9 National MSP-valued gross value")
    a, b = q9.iloc[0], q9[q9.crop_year == 2018].iloc[0]
    L.append(f"- {int(a.crop_year)}: Rs {a.nominal:,.0f} cr -> 2018: Rs {b.nominal:,.0f} cr nominal "
             f"(x{b.nominal/a.nominal:.1f}); real, CPI-deflated: x{b.real_cpi_2018/a.real_cpi_2018:.2f}; volume at constant 2018-19 MSP: x{b.volume_index_2004_100/100:.2f}")
    L.append("\n## Q10 Most volatile crops in Maharashtra APMCs (median CV of monthly modal price)")
    for _, r in q10.head(5).iterrows():
        L.append(f"- {r.crop_name}: CV {r.median_cv_pct}% across {r.markets} APMCs")
    (RESULTS / "findings.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
