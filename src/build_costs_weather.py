"""
Cost of cultivation (DES/CACP, state x crop, 2008-09..2013-14) and IMD rainfall.

NO projection or interpolation of costs is performed. Profit is computed only where a
state x crop x year cost observation exists.
"""
import re
import numpy as np
import pandas as pd
from .config import RAW, PROC, STATE_TO_SUBDIVISIONS, norm_state

COC_CROP = {"Paddy": "Rice", "Wheat": "Wheat", "Maize": "Maize", "Gram": "Gram", "Arhar": "Arhar/Tur",
            "Moong": "Moong", "Groundnut": "Groundnut", "Rapeseed And Mustard": "Rapeseed & Mustard",
            "Cotton": "Cotton", "Sugarcane": "Sugarcane"}


def build_costs():
    dim_crop = pd.read_csv(PROC / "dim_crop.csv")
    dim_state = pd.read_csv(PROC / "dim_state.csv")
    raw = pd.read_csv(RAW / "culti_cost.csv")
    recs = []
    for _, r in raw.iterrows():
        crop = COC_CROP.get(str(r["Crop"]).strip())
        state = norm_state(r["State/ UT Name"])
        for col in raw.columns[2:]:
            m = re.search(r"(A2\+FL|C2) - (\d{4})-(\d{2})", col)
            kind = ("a2fl_per_ha" if m.group(1) == "A2+FL" else ("c2_per_qtl" if "Quintal" in col else "c2_per_ha"))
            recs.append(dict(crop_name=crop, state_name=state, crop_year=int(m.group(2)), measure=kind,
                             value=pd.to_numeric(r[col], errors="coerce")))
    long = pd.DataFrame(recs)
    coc = long.pivot_table(index=["crop_name", "state_name", "crop_year"], columns="measure",
                           values="value").reset_index()
    coc.columns.name = None
    coc["implied_yield_qtl_per_ha"] = coc["c2_per_ha"] / coc["c2_per_qtl"]   # approximate (C2/qtl is net of by-product)
    coc["crop_year_label"] = coc.crop_year.astype(str) + "-" + (coc.crop_year + 1).astype(str).str[-2:]
    coc = coc.merge(dim_crop[["crop_id", "crop_name"]], on="crop_name").merge(
        dim_state[["state_id", "state_name"]], on="state_name")
    coc["source"] = "DES/CACP Cost of Cultivation Scheme via data.gov.in (culti_cost.csv)"
    coc.insert(0, "cost_id", range(1, len(coc) + 1))
    coc.to_csv(PROC / "fact_cost_of_cultivation.csv", index=False)
    print("cost rows", len(coc), "| crops", coc.crop_name.nunique(), "| states", coc.state_name.nunique())
    return coc


def imd_category(dep):
    if pd.isna(dep):
        return None
    if dep >= 60: return "Large excess"
    if dep >= 20: return "Excess"
    if dep > -20: return "Normal"
    if dep > -60: return "Deficient"
    return "Large deficient"


def build_weather():
    r = pd.read_csv(RAW / "rainfall_in_india.csv").rename(columns={"SUBDIVISION": "subdivision", "DIVISION": "subdivision", "YEAR": "year"})
    r["subdivision"] = r["subdivision"].str.strip()
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    r["jjas_mm"] = r[["JUN", "JUL", "AUG", "SEP"]].sum(axis=1, min_count=4)
    r["ond_mm"] = r[["OCT", "NOV", "DEC"]].sum(axis=1, min_count=3)
    r["jf_mm"] = r[["JAN", "FEB"]].sum(axis=1, min_count=2)
    r["annual_mm"] = r[months].sum(axis=1, min_count=12)
    r = r.sort_values(["subdivision", "year"])
    # Rabi-season rain for crop year Y = Oct-Dec of Y + Jan-Feb of Y+1
    r["jf_next_mm"] = r.groupby("subdivision")["jf_mm"].shift(-1)
    r["rabi_rain_mm"] = r["ond_mm"] + r["jf_next_mm"]
    base = r[r.year.between(1951, 2000)].groupby("subdivision")[["jjas_mm", "rabi_rain_mm", "annual_mm"]].mean()
    for col in ["jjas_mm", "rabi_rain_mm", "annual_mm"]:
        r[col.replace("_mm", "_normal_mm")] = r["subdivision"].map(base[col])
        r[col.replace("_mm", "_dep_pct")] = (r[col] / r[col.replace("_mm", "_normal_mm")] - 1) * 100
    r["jjas_category"] = r["jjas_dep_pct"].map(imd_category)
    sub = r[["subdivision", "year"] + months + ["jjas_mm", "ond_mm", "rabi_rain_mm", "annual_mm",
                                               "jjas_normal_mm", "jjas_dep_pct", "jjas_category",
                                               "rabi_rain_normal_mm", "rabi_rain_dep_pct",
                                               "annual_normal_mm", "annual_dep_pct"]].copy()
    sub.insert(0, "weather_id", range(1, len(sub) + 1))
    sub.to_csv(PROC / "fact_weather_subdivision.csv", index=False)

    # state x year = mean of the state's subdivisions (unweighted)
    dim_state = pd.read_csv(PROC / "dim_state.csv")
    rows = []
    for st, subs in STATE_TO_SUBDIVISIONS.items():
        x = r[r.subdivision.isin(subs)].groupby("year")[["jjas_mm", "rabi_rain_mm", "annual_mm",
                                                           "jjas_normal_mm", "rabi_rain_normal_mm",
                                                           "annual_normal_mm"]].mean()
        x["state_name"], x["n_subdivisions"] = st, len(subs)
        rows.append(x.reset_index())
    stw = pd.concat(rows, ignore_index=True).rename(columns={"year": "crop_year"})
    stw["jjas_dep_pct"] = (stw.jjas_mm / stw.jjas_normal_mm - 1) * 100
    stw["rabi_rain_dep_pct"] = (stw.rabi_rain_mm / stw.rabi_rain_normal_mm - 1) * 100
    stw["annual_dep_pct"] = (stw.annual_mm / stw.annual_normal_mm - 1) * 100
    stw["jjas_category"] = stw["jjas_dep_pct"].map(imd_category)
    stw["rainfall_basis"] = np.where(stw.n_subdivisions > 1, "Mean of IMD subdivisions (unweighted)",
                                     "Single IMD subdivision (may be shared with neighbouring states)")
    stw = stw.merge(dim_state[["state_id", "state_name"]], on="state_name")
    stw = stw[stw.crop_year >= 1990]
    stw.insert(0, "state_weather_id", range(1, len(stw) + 1))
    stw.to_csv(PROC / "fact_weather_state.csv", index=False)
    print("subdivision-years", len(sub), "| state-years", len(stw))


if __name__ == "__main__":
    build_costs()
    build_weather()
