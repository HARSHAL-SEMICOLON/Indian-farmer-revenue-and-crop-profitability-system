"""
Mandi price layer.

Sources (both Rs/quintal):
  1. Maharashtra APMC monthly arrivals & prices, Sep-2014 .. Nov-2016 (CMO dataset, 349 APMCs)
  2. AGMARKNET 'Current daily price of various commodities from various markets', snapshot 30-Sep-2024
     (data.gov.in resource 9ef84268-d588-465a-a308-a864a43d0070), 27 states, ~1,196 markets
  3. Same AGMARKNET feed accumulated daily, 21-Jul-2026 .. 24-Sep-2026 (~2,700 markets, 30 states)

Only commodities that map unambiguously to an analysed crop are kept. Each row carries a
price_form and an msp_comparable flag: e.g. milled rice, basmati paddy, ginned cotton, dal
are NOT comparable with the MSP (which is for FAQ paddy / kapas / whole grain).
"""
import numpy as np
import pandas as pd
from .config import RAW, PROC, CURATED, norm_state

# commodity -> (crop_name, price_form, msp_comparable)
CMO_MAP = {
    "PADDY-UNHUSKED": ("Rice", "Paddy (unhusked)", True),
    "RICE(PADDY-HUS)": ("Rice", "Milled rice", False),
    "WHEAT(HUSKED)": ("Wheat", "Wheat grain", True),
    "SORGUM(JAWAR)": ("Jowar", "Jowar (mixed varieties)", True),
    "BAJRI": ("Bajra", "Bajra", True),
    "MAIZE": ("Maize", "Maize", True),
    "GRAM": ("Gram", "Gram (whole)", True),
    "PIGEON PEA (TUR)": ("Arhar/Tur", "Tur (whole)", True),
    "GREEN GRAM": ("Moong", "Moong (whole)", True),
    "BLACK GRAM": ("Urad", "Urad (whole)", True),
    "LENTIL": ("Masoor", "Masur (whole)", True),
    "GROUND NUT PODS (DRY)": ("Groundnut", "Groundnut in shell", True),
    "SOYBEAN": ("Soyabean", "Soyabean", True),
    "MUSTARD": ("Rapeseed & Mustard", "Mustard seed", True),
    "SUNFLOWER": ("Sunflower", "Sunflower seed", True),
    "SESAMUM": ("Sesamum", "Sesamum", True),
    "NIGER-SEED": ("Nigerseed", "Nigerseed", True),
    "SAFFLOWER": ("Safflower", "Safflower", True),
    "COTTON": ("Cotton", "Kapas (seed cotton)", True),
    "SUGARCANE": ("Sugarcane", "Sugarcane (mandi)", False),   # cane is sold to mills at FRP/SAP, mandi price not comparable
    "ONION": ("Onion", "Onion", False),
    "POTATO": ("Potato", "Potato", False),
    "CHILLIES(RED)": ("Dry Chillies", "Dry red chillies", False),
    "TURMERIC": ("Turmeric", "Turmeric", False),
}
AGM_MAP = {
    "Paddy(Dhan)(Common)": ("Rice", "Paddy (common)", True),
    "Paddy(Dhan)(Basmati)": ("Rice", "Paddy (basmati)", False),
    "Rice": ("Rice", "Milled rice", False),
    "Wheat": ("Wheat", "Wheat grain", True),
    "Maize": ("Maize", "Maize", True),
    "Bajra(Pearl Millet/Cumbu)": ("Bajra", "Bajra", True),
    "Jowar(Sorghum)": ("Jowar", "Jowar (mixed varieties)", True),
    "Ragi (Finger Millet)": ("Ragi", "Ragi", True),
    "Barley (Jau)": ("Barley", "Barley", True),
    "Bengal Gram(Gram)(Whole)": ("Gram", "Gram (whole)", True),
    "Arhar (Tur/Red Gram)(Whole)": ("Arhar/Tur", "Tur (whole)", True),
    "Green Gram (Moong)(Whole)": ("Moong", "Moong (whole)", True),
    "Black Gram (Urd Beans)(Whole)": ("Urad", "Urad (whole)", True),
    "Lentil (Masur)(Whole)": ("Masoor", "Masur (whole)", True),
    "Groundnut": ("Groundnut", "Groundnut in shell", True),
    "Mustard": ("Rapeseed & Mustard", "Mustard seed", True),
    "Soyabean": ("Soyabean", "Soyabean", True),
    "Sunflower": ("Sunflower", "Sunflower seed", True),
    "Sesamum(Sesame,Gingelly,Til)": ("Sesamum", "Sesamum", True),
    "Cotton": ("Cotton", "Kapas (seed cotton)", True),
    "Jute": ("Jute", "Raw jute", True),
    "Onion": ("Onion", "Onion", False),
    "Potato": ("Potato", "Potato", False),
    "Dry Chillies": ("Dry Chillies", "Dry red chillies", False),
    "Turmeric": ("Turmeric", "Turmeric", False),
    # labels used by the 2026 feed
    "Paddy(Common)": ("Rice", "Paddy (common)", True),
    "Paddy(Basmati)": ("Rice", "Paddy (basmati)", False),
    "Red gram/Arhar/Tur(whole)": ("Arhar/Tur", "Tur (whole)", True),
    "Green Gram(Moong)(Whole)": ("Moong", "Moong (whole)", True),
    "Black Gram(Urd Beans)(Whole)": ("Urad", "Urad (whole)", True),
    "Lentil(Masur)(Whole)": ("Masoor", "Masur (whole)", True),
    "Ragi(Finger Millet)": ("Ragi", "Ragi", True),
    "Barley(Jau)": ("Barley", "Barley", True),
    "Sunflower/Sunflower Seed": ("Sunflower", "Sunflower seed", True),
    "Safflower": ("Safflower", "Safflower", True),
    "Niger Seed(Ramtil)": ("Nigerseed", "Nigerseed", True),
}
# varieties that change the commodity form -> not MSP-comparable
NON_COMPARABLE_VARIETY = ["kernel", "split", "ginned cotton", "organic"]
KHARIF_KEYS = {"Rice", "Maize", "Jowar", "Bajra", "Ragi", "Arhar/Tur", "Moong", "Urad", "Groundnut",
               "Soyabean", "Sunflower", "Sesamum", "Nigerseed", "Cotton", "Jute"}
RABI_KEYS = {"Wheat", "Barley", "Gram", "Masoor", "Rapeseed & Mustard", "Safflower"}


def msp_crop_year(crop, ts):
    """Crop year whose MSP applies on a given sale date (marketing-season rule)."""
    y, m = ts.year, ts.month
    if crop in KHARIF_KEYS:            # KMS runs Oct(Y) .. Sep(Y+1)
        return y if m >= 10 else y - 1
    if crop in RABI_KEYS:              # RMS (Y+1)-(Y+2) runs Apr(Y+1) .. Mar(Y+2) for crop year Y
        return y - 1 if m >= 4 else y - 2
    return np.nan


def main():
    dim_crop = pd.read_csv(PROC / "dim_crop.csv")
    msp = pd.read_csv(CURATED / "msp_official_curated.csv")
    crop_id = dim_crop.set_index("crop_name")["crop_id"].to_dict()
    msp_key = dim_crop.set_index("crop_name")["msp_key"].to_dict()
    msp_lookup = msp.set_index(["msp_key", "crop_year"])["msp_effective"].to_dict()
    issues = []

    # ---------------- 1. Maharashtra CMO monthly ---------------------------------------------------
    c = pd.read_csv(RAW / "mandi_monthly_cmo.csv")
    c["commodity_raw"] = c["Commodity"].str.strip()
    c["key"] = c["commodity_raw"].str.upper()
    c = c[c["key"].isin(CMO_MAP)].copy()
    c[["crop_name", "price_form", "msp_comparable"]] = pd.DataFrame(c["key"].map(CMO_MAP).tolist(), index=c.index)
    p1 = pd.DataFrame({
        "source_dataset": "MH APMC monthly (CMO) 2014-16", "granularity": "Monthly",
        "state_name": c["state_name"].map(norm_state), "district_name": c["district_name"].str.strip().str.title(),
        "market_name": c["APMC"].str.strip().str.title(), "crop_name": c["crop_name"],
        "commodity_raw": c["commodity_raw"], "variety": "", "price_form": c["price_form"],
        "msp_comparable": c["msp_comparable"], "price_date": pd.to_datetime(c["date"] + "-01"),
        "arrivals_qtl": c["arrivals_in_qtl"], "min_price": c["min_price"], "max_price": c["max_price"],
        "modal_price": c["modal_price"]})
    # same market/commodity/month can appear twice due to case-duplicated commodity labels
    p1 = p1.groupby(["source_dataset", "granularity", "state_name", "district_name", "market_name", "crop_name",
                     "price_form", "msp_comparable", "price_date"], as_index=False).agg(
        commodity_raw=("commodity_raw", "first"), variety=("variety", "first"), arrivals_qtl=("arrivals_qtl", "sum"),
        min_price=("min_price", "min"), max_price=("max_price", "max"), modal_price=("modal_price", "median"))

    # ---------------- 2 & 3. AGMARKNET daily feeds (2024 snapshot, 2026 Jul-Sep history) ------------
    DEDUP = {}

    def load_agm(path, label):
        a = pd.read_csv(path, low_memory=False)
        a.columns = [c.replace("_x0020_", "_").lower() for c in a.columns]   # Min_x0020_Price -> min_price
        for c in ["state", "district", "market", "commodity", "variety", "grade"]:
            if c in a.columns:
                a[c] = a[c].astype(str).str.strip()
        key = ["state", "district", "market", "commodity", "variety", "arrival_date"]
        # One quote per market x commodity x variety x day. The same price is often reported under two grades;
        # MSP is defined for FAQ (fair average quality), so FAQ is kept when both exist.
        n_before = len(a)
        if "grade" in a.columns:
            a = a.assign(_faq=(a["grade"].str.upper() != "FAQ").astype(int)).sort_values("_faq").drop(columns="_faq")
        a = a.drop_duplicates([c for c in key if c in a.columns])
        DEDUP[label] = n_before - len(a)
        a = a[a["commodity"].isin(AGM_MAP)].copy()
        a[["crop_name", "price_form", "msp_comparable"]] = pd.DataFrame(a["commodity"].map(AGM_MAP).tolist(), index=a.index)
        nc = a["variety"].astype(str).str.lower().str.contains("|".join(NON_COMPARABLE_VARIETY), na=False)
        a.loc[nc, "msp_comparable"] = False
        a.loc[nc, "price_form"] = a.loc[nc, "price_form"] + " - " + a.loc[nc, "variety"].astype(str)
        return pd.DataFrame({
            "source_dataset": label, "granularity": "Daily",
            "state_name": a["state"].map(norm_state), "district_name": a["district"].astype(str).str.strip().str.title(),
            "market_name": a["market"].astype(str).str.strip().str.title(), "crop_name": a["crop_name"],
            "commodity_raw": a["commodity"], "variety": a["variety"], "price_form": a["price_form"],
            "msp_comparable": a["msp_comparable"], "price_date": pd.to_datetime(a["arrival_date"], format="%d/%m/%Y"),
            "arrivals_qtl": np.nan, "min_price": a["min_price"], "max_price": a["max_price"],
            "modal_price": a["modal_price"]})

    p2 = load_agm(RAW / "mandi_dataset_2024.csv", "AGMARKNET daily snapshot 30-Sep-2024")
    p3 = load_agm(RAW / "agmarknet_daily_2026.csv.gz", "AGMARKNET daily Jul-Sep 2026")

    p = pd.concat([p1, p2, p3], ignore_index=True)
    n0 = len(p)

    # ---------------- validity rules --------------------------------------------------------------
    p["dq_flag"] = "ok"
    bad_zero = p["modal_price"] <= 0
    p.loc[bad_zero, "dq_flag"] = "excluded: modal <= 0"
    incons = (p["min_price"] > p["modal_price"]) | (p["modal_price"] > p["max_price"]) | (p["min_price"] <= 0)
    p.loc[incons & (p.dq_flag == "ok"), "dq_flag"] = "flag: min/modal/max inconsistent (spread not computed)"
    # median within each dataset: price levels differ across years, so never pool 2014-16 with 2026
    meds = p[~bad_zero].groupby(["source_dataset", "crop_name", "price_form"])["modal_price"].median()
    med = pd.Series([meds.get((sd, cn, pf), np.nan) for sd, cn, pf in zip(p["source_dataset"], p["crop_name"], p["price_form"])], index=p.index)
    outl = (p["modal_price"] > 5 * med) | (p["modal_price"] < med / 5)
    p.loc[outl & (p.dq_flag == "ok"), "dq_flag"] = "excluded: modal >5x or <1/5 of commodity median"
    p.loc[outl & p.dq_flag.str.startswith("flag"), "dq_flag"] = "excluded: modal >5x or <1/5 of commodity median"

    issues = p[p.dq_flag != "ok"][["source_dataset", "market_name", "crop_name", "price_date", "min_price",
                                   "modal_price", "max_price", "dq_flag"]]
    ok_spread = p.dq_flag == "ok"
    p["price_spread"] = np.where(ok_spread, p["max_price"] - p["min_price"], np.nan)
    p["price_spread_pct"] = np.where(ok_spread, p["price_spread"] / p["modal_price"] * 100, np.nan)

    # ---------------- MSP comparison -------------------------------------------------------------
    p["msp_crop_year"] = [msp_crop_year(cn, ts) for cn, ts in zip(p["crop_name"], p["price_date"])]
    p["msp_key"] = p["crop_name"].map(msp_key)
    p["msp_applicable"] = [msp_lookup.get((k, int(y))) if (isinstance(k, str) and pd.notna(y)) else np.nan
                           for k, y in zip(p["msp_key"], p["msp_crop_year"])]
    valid_cmp = p["msp_comparable"].astype(bool) & p["msp_applicable"].notna() & ~p.dq_flag.str.startswith("excluded")
    p.loc[~valid_cmp, "msp_applicable"] = np.nan
    p["modal_vs_msp_pct"] = (p["modal_price"] / p["msp_applicable"] - 1) * 100
    p["modal_below_msp"] = np.where(p["msp_applicable"].notna(), p["modal_price"] < p["msp_applicable"], np.nan)
    # price distribution relative to MSP (for histograms): band label + sort order
    bands = [(-np.inf, -20, "1 >20% below MSP"), (-20, -10, "2 10-20% below"), (-10, 0, "3 0-10% below"),
             (0, 10, "4 0-10% above"), (10, np.inf, "5 >10% above MSP")]
    v = p["modal_vs_msp_pct"]
    p["msp_price_band"] = np.select([(v >= lo) & (v < hi) for lo, hi, _ in bands], [b[2:] for *_, b in bands], None)
    p["msp_price_band_order"] = np.select([(v >= lo) & (v < hi) for lo, hi, _ in bands], [int(b[0]) for *_, b in bands], 0)
    p["msp_price_band_order"] = p["msp_price_band_order"].where(v.notna()).astype("Int64")

    # ---------------- dimensions -----------------------------------------------------------------
    mk = p[["market_name", "district_name", "state_name", "source_dataset"]].drop_duplicates(
        ["market_name", "district_name", "state_name"]).sort_values(["state_name", "district_name", "market_name"])
    mk = mk.reset_index(drop=True)
    mk.insert(0, "market_id", range(1, len(mk) + 1))
    mk = mk.rename(columns={"source_dataset": "first_seen_in"})
    dim_state = pd.read_csv(PROC / "dim_state.csv")
    mk = mk.merge(dim_state[["state_id", "state_name"]], on="state_name", how="left")
    unmatched = sorted(mk.loc[mk.state_id.isna(), "state_name"].unique())
    if unmatched:
        print("markets in states without a dim_state row:", unmatched)
    p = p.merge(mk[["market_id", "market_name", "district_name", "state_name"]],
                on=["market_name", "district_name", "state_name"])
    p["crop_id"] = p["crop_name"].map(crop_id)

    dates = pd.DataFrame({"price_date": sorted(p["price_date"].unique())})
    dates["date_key"] = dates.price_date.dt.strftime("%Y%m%d").astype(int)
    dates["year"] = dates.price_date.dt.year
    dates["month"] = dates.price_date.dt.month
    dates["month_name"] = dates.price_date.dt.strftime("%b")
    dates["year_month"] = dates.price_date.dt.strftime("%Y-%m")
    dates["agri_year"] = np.where(dates.month >= 7, dates.year, dates.year - 1)
    dates["agri_year_label"] = dates.agri_year.astype(str) + "-" + (dates.agri_year + 1).astype(str).str[-2:]
    dates["season_window"] = np.select([dates.month.between(6, 10), dates.month.isin([11, 12, 1, 2, 3])],
                                       ["Kharif window (Jun-Oct)", "Rabi window (Nov-Mar)"], "Zaid/Summer (Apr-May)")
    p = p.merge(dates[["price_date", "date_key"]], on="price_date")

    p = p.sort_values(["source_dataset", "crop_id", "market_id", "date_key"]).reset_index(drop=True)
    p.insert(0, "price_id", range(1, len(p) + 1))
    cols = ["price_id", "market_id", "crop_id", "date_key", "source_dataset", "granularity", "commodity_raw",
            "variety", "price_form", "msp_comparable", "arrivals_qtl", "min_price", "max_price", "modal_price",
            "price_spread", "price_spread_pct", "msp_crop_year", "msp_applicable", "modal_vs_msp_pct",
            "modal_below_msp", "msp_price_band", "msp_price_band_order", "dq_flag"]
    p[cols].to_csv(PROC / "fact_market_price.csv", index=False)
    mk.to_csv(PROC / "dim_market.csv", index=False)
    dates.to_csv(PROC / "dim_date.csv", index=False)
    issues.to_csv(PROC / "dq_price_issues.csv", index=False)
    pd.DataFrame([{"source_dataset": k, "rows_dropped": v} for k, v in DEDUP.items()]).to_csv(PROC / "dq_price_dedup.csv", index=False)
    print({"price_rows": len(p), "rows_in": n0, "markets": len(mk), "flagged_or_excluded": len(issues)})
    print(issues.dq_flag.value_counts())


if __name__ == "__main__":
    main()
