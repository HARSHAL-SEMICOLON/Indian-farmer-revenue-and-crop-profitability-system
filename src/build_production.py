"""
Production layer: DES APY district x season x crop (1997-2019, plus any newer DES files dropped into data/raw/).

Newer years: download district-wise crop production from data.desagri.gov.in (or UPAg) as CSV and save it as
data/raw/apy_district_extra_<anything>.csv. Column names are matched flexibly (State, District, Crop, Year or
Crop_Year such as "2020-21", Season, Area, Production, optional "Production Units"). Rows whose production unit
doesn't match the crop's APY unit are excluded, and a year is used only if enough districts report it.

Outputs
  dim_crop, dim_state, dim_location (district), dim_year
  fact_production   (district x crop x crop_year x season)
  dq_production_issues (rows excluded / flagged and why)
"""
import numpy as np
import pandas as pd
from .config import (cpi_deflator_2018, RAW, PROC, CROPS, CROP_COLS, STATE_REGION, STATE_TO_SUBDIVISIONS, norm_state,
                    PROVISIONAL_YEARS, MSP_VALUATION_YEARS)

# Plausible upper bound on yield in APY units per ha (t/ha; bales/ha for cotton & jute).
MAX_YIELD = {"Rice": 8, "Wheat": 8, "Maize": 12, "Jowar": 6, "Bajra": 6, "Ragi": 6, "Barley": 6,
             "Gram": 4, "Arhar/Tur": 4, "Moong": 3, "Urad": 3, "Masoor": 4, "Groundnut": 6,
             "Rapeseed & Mustard": 4, "Soyabean": 5, "Sunflower": 4, "Sesamum": 3, "Nigerseed": 2,
             "Safflower": 3, "Cotton": 15, "Jute": 25, "Sugarcane": 200, "Onion": 60, "Potato": 60,
             "Dry Chillies": 8, "Turmeric": 30}

STATE_GROUP = {"Telangana": "Andhra Pradesh + Telangana", "Andhra Pradesh": "Andhra Pradesh + Telangana",
               "Chhattisgarh": "Madhya Pradesh + Chhattisgarh", "Madhya Pradesh": "Madhya Pradesh + Chhattisgarh",
               "Jharkhand": "Bihar + Jharkhand", "Bihar": "Bihar + Jharkhand",
               "Uttarakhand": "Uttar Pradesh + Uttarakhand", "Uttar Pradesh": "Uttar Pradesh + Uttarakhand",
               "Ladakh": "Jammu and Kashmir + Ladakh", "Jammu and Kashmir": "Jammu and Kashmir + Ladakh"}


ALIASES = {"state": ["state", "state_name", "state name"], "district": ["district", "district_name", "district name"],
           "crop": ["crop", "crop_name", "crop name"], "year": ["year", "crop_year", "crop year"],
           "season": ["season"], "area": ["area", "area (hectare)", "area_ha"],
           "production": ["production", "production (tonnes)"], "production_units": ["production units", "production_units", "production unit"]}
# APY crop names in newer DES exports that differ from the 1997-2019 file
CROP_RENAME = {"Cotton(lint)": "Cotton(Lint)", "Cotton": "Cotton(Lint)", "Nigerseed": "Niger Seed", "Niger seed": "Niger Seed",
               "Moong": "Moong(Green Gram)", "Rapeseed & Mustard": "Rapeseed &Mustard", "Rapeseed and Mustard": "Rapeseed &Mustard",
               "Soybean": "Soyabean", "Masur": "Masoor", "Lentil": "Masoor", "Arhar": "Arhar/Tur", "Tur": "Arhar/Tur"}


def normalize_apy(df, crops):
    """Map a DES/UPAg district production export onto the base APY columns and check units.
    Returns (rows in base format, rows rejected for unit mismatch)."""
    cols = {c.strip().lower(): c for c in df.columns}
    pick = {}
    for k, names in ALIASES.items():
        for n in names:
            if n in cols:
                pick[k] = cols[n]
                break
    missing = {"state", "district", "crop", "year", "season", "area", "production"} - set(pick)
    if missing:
        raise ValueError(f"supplementary APY file is missing columns: {sorted(missing)}")
    out = pd.DataFrame({k: df[v] for k, v in pick.items()})
    out["year"] = out["year"].astype(str).str.extract(r"(\d{4})")[0].astype(int)
    out["crop"] = out["crop"].astype(str).str.strip().replace(CROP_RENAME)
    for c in ["area", "production"]:
        out[c] = pd.to_numeric(out[c].astype(str).str.replace(",", ""), errors="coerce")
    bad = pd.DataFrame(columns=out.columns)
    if "production_units" in out:
        unit = crops.set_index("apy_name")["apy_unit"].str.lower()
        expect_bales = out["crop"].map(unit).fillna("").str.contains("bales")
        u = out["production_units"].astype(str).str.lower()
        ok = np.where(expect_bales, u.str.contains("bale"), u.str.contains("tonne"))
        bad, out = out[~ok].copy(), out[ok].copy()
        out = out.drop(columns="production_units")
        bad = bad.drop(columns="production_units")
    return out, bad


def main():
    crops = pd.DataFrame(CROPS, columns=CROP_COLS)
    crops.insert(0, "crop_id", range(1, len(crops) + 1))
    crops["is_msp_crop"] = crops["msp_key"].notna()

    raw = pd.read_csv(RAW / "apy_district_1997_2019.csv").drop(columns=["Unnamed: 0"], errors="ignore")
    issues = []
    extra = []
    for f in sorted(RAW.glob("apy_district_extra*.csv")):
        e, bad_unit = normalize_apy(pd.read_csv(f, low_memory=False), crops)
        e = e[e["year"] > raw["year"].max() - 1]          # only add years the base file lacks (or has incomplete)
        if len(bad_unit):
            bad_unit["issue"], bad_unit["action"] = f"Production unit does not match crop's APY unit ({f.name})", "excluded"
            issues.append(bad_unit)
        print(f"  + {f.name}: {len(e):,} rows, crop years {e.year.min()}-{e.year.max()}")
        extra.append(e)
    if extra:
        new = pd.concat(extra, ignore_index=True)
        raw = pd.concat([raw[~raw["year"].isin(new["year"].unique())], new], ignore_index=True)
    n_raw = len(raw)
    raw["state"] = raw["state"].map(norm_state)
    raw["district"] = raw["district"].astype(str).str.strip().str.title()
    raw["season"] = raw["season"].astype(str).str.strip()
    raw["crop"] = raw["crop"].astype(str).str.strip()

    def log(df, issue, action):
        if len(df):
            x = df[["state", "district", "crop", "year", "season", "area", "production"]].copy()
            x["issue"], x["action"] = issue, action
            issues.append(x)

    # restrict to analysed crops
    d = raw[raw["crop"].isin(crops["apy_name"])].copy()
    d = d.merge(crops[["crop_id", "crop_name", "apy_name", "to_price_qtl_factor"]], left_on="crop", right_on="apy_name")

    # 1. incomplete years: fewer than 60% of the usual number of reporting districts
    per_year = d.groupby("year")["district"].nunique()
    typical = per_year.median()
    thin = per_year[per_year < 0.6 * typical].index
    for y in thin:
        log(d[d.year == y], f"Crop year {y} reported by only {per_year[y]} districts (typical {typical:.0f})", "excluded")
    d = d[~d.year.isin(thin)]

    # 2. conflicting duplicate keys
    key = ["state", "district", "crop", "year", "season"]
    dupmask = d.duplicated(key, keep=False)
    log(d[dupmask], "Duplicate district-crop-year-season key with conflicting values", "excluded (both rows)")
    d = d[~dupmask]

    # 3. non-positive area
    log(d[d.area <= 0], "Area <= 0", "excluded")
    d = d[d.area > 0]

    d["yield_apy_per_ha"] = d["production"] / d["area"]
    d["max_yield"] = d["crop_name"].map(MAX_YIELD)
    bad = d["yield_apy_per_ha"] > d["max_yield"]
    log(d[bad], "Implausible yield (above agronomic ceiling for crop)", "excluded")
    d = d[~bad]

    d["dq_flag"] = np.where(d["production"] == 0, "zero_production", "ok")

    # ----- dimensions -------------------------------------------------------------------------------
    states = sorted(set(d["state"]) | set(STATE_TO_SUBDIVISIONS))
    dim_state = pd.DataFrame({"state_name": states})
    dim_state.insert(0, "state_id", range(1, len(dim_state) + 1))
    dim_state["region"] = dim_state["state_name"].map(STATE_REGION).fillna("Other")
    dim_state["state_group"] = dim_state["state_name"].map(STATE_GROUP).fillna(dim_state["state_name"])
    dim_state["imd_subdivisions"] = dim_state["state_name"].map(
        lambda s: "; ".join(STATE_TO_SUBDIVISIONS.get(s, [])))

    loc = d[["state", "district"]].drop_duplicates().sort_values(["state", "district"]).reset_index(drop=True)
    loc.insert(0, "location_id", range(1, len(loc) + 1))
    loc = loc.rename(columns={"state": "state_name", "district": "district_name"}).merge(
        dim_state[["state_id", "state_name"]], on="state_name")
    loc["district_key"] = loc["state_name"] + " | " + loc["district_name"]
    first_last = d.groupby(["state", "district"]).year.agg(["min", "max"]).reset_index()
    loc = loc.merge(first_last.rename(columns={"state": "state_name", "district": "district_name",
                                               "min": "first_year", "max": "last_year"}),
                    on=["state_name", "district_name"])

    years = pd.DataFrame({"crop_year": range(1990, 2027)})
    years["crop_year_label"] = years.crop_year.astype(str) + "-" + (years.crop_year + 1).astype(str).str[-2:]
    years["kharif_marketing_season"] = "KMS " + years["crop_year_label"]
    years["rabi_marketing_season"] = "RMS " + (years.crop_year + 1).astype(str) + "-" + (years.crop_year + 2).astype(str).str[-2:]
    years["has_production_data"] = years.crop_year.isin(d["year"].unique())
    years["in_msp_valuation_window"] = years.crop_year.isin(MSP_VALUATION_YEARS)
    years["is_provisional"] = years.crop_year.isin(PROVISIONAL_YEARS)
    years["has_cost_data"] = years.crop_year.between(2008, 2013)
    years["has_rainfall_data"] = years.crop_year.between(1997, 2015)
    years["cpi_deflator_2018_100"] = years.crop_year.map(cpi_deflator_2018())
    years["decade"] = (years.crop_year // 5 * 5).astype(str) + "-" + (years.crop_year // 5 * 5 + 4).astype(str)

    # ----- fact_production --------------------------------------------------------------------------
    d = d.merge(loc[["location_id", "state_name", "district_name"]],
                left_on=["state", "district"], right_on=["state_name", "district_name"])
    fact = pd.DataFrame({
        "location_id": d["location_id"], "crop_id": d["crop_id"], "crop_year": d["year"],
        "season": d["season"], "area_ha": d["area"], "production_apy_unit": d["production"],
        "production_price_qtl": d["production"] * d["to_price_qtl_factor"],
        "yield_apy_unit_per_ha": d["yield_apy_per_ha"], "dq_flag": d["dq_flag"],
    }).sort_values(["crop_id", "location_id", "crop_year", "season"]).reset_index(drop=True)
    fact.insert(0, "production_id", range(1, len(fact) + 1))

    dq = pd.concat(issues, ignore_index=True) if issues else pd.DataFrame()

    crops.to_csv(PROC / "dim_crop.csv", index=False)
    dim_state.to_csv(PROC / "dim_state.csv", index=False)
    loc.to_csv(PROC / "dim_location.csv", index=False)
    years.to_csv(PROC / "dim_year.csv", index=False)
    fact.to_csv(PROC / "fact_production.csv", index=False)
    dq.to_csv(PROC / "dq_production_issues.csv", index=False)
    summary = {"raw_rows_all_crops": n_raw, "rows_analysed_crops": int(raw["crop"].isin(crops["apy_name"]).sum()),
               "fact_rows": len(fact), "excluded_rows": len(dq), "districts": len(loc), "states": d.state.nunique()}
    print(summary)
    print(dq.groupby("issue").size() if len(dq) else "no issues")
    return summary


if __name__ == "__main__":
    main()
