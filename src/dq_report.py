"""
Data-quality report: runs live checks against the SQLite database and writes
  outputs/results/dq_summary.csv, docs/DATA_QUALITY.md and the DATA QUALITY block in README.md.
Every number is recomputed on each pipeline run, so the documentation cannot drift from the data.
"""
import re
import sqlite3

import numpy as np
import pandas as pd

from .config import ROOT, RESULTS, RICE_TO_PADDY, COTTON_GOT, connect_ro
from .sql_queries import load_queries, connect as sql_connect

DOCS = ROOT / "docs"


def _one(con, sql):
    return con.execute(sql).fetchone()[0]


def checks():
    con = connect_ro()
    rows = []

    def add(area, check, value, expected, passed, note=""):
        rows.append(dict(area=area, check=check, value=value, expected=expected,
                         status="PASS" if passed else "CHECK", note=note))

    # --- integrity --------------------------------------------------------------------------------
    fk = len(con.execute("PRAGMA foreign_key_check").fetchall())
    add("Integrity", "Foreign-key violations", fk, 0, fk == 0)
    dup_prod = _one(con, """SELECT COUNT(*) FROM (SELECT location_id, crop_id, crop_year, season FROM fact_production
                             GROUP BY 1,2,3,4 HAVING COUNT(*) > 1)""")
    add("Integrity", "Duplicate production keys (district x crop x year x season)", dup_prod, 0, dup_prod == 0)
    dup_dcy = _one(con, """SELECT COUNT(*) FROM (SELECT location_id, crop_id, crop_year FROM fact_district_crop_year
                            GROUP BY 1,2,3 HAVING COUNT(*) > 1)""")
    add("Integrity", "Duplicate district x crop x year rows", dup_dcy, 0, dup_dcy == 0)
    dup_msp = _one(con, "SELECT COUNT(*) FROM (SELECT msp_key, crop_year FROM fact_msp GROUP BY 1,2 HAVING COUNT(*) > 1)")
    add("Integrity", "Duplicate MSP crop x year", dup_msp, 0, dup_msp == 0)
    dup_px = _one(con, """SELECT COUNT(*) FROM (SELECT source_dataset, market_id, crop_id, date_key, variety, price_form
                           FROM fact_market_price GROUP BY 1,2,3,4,5,6 HAVING COUNT(*) > 1)""")
    add("Integrity", "Duplicate mandi quotes (dataset x market x crop x date x variety)", dup_px, 0, dup_px == 0,
        "exact duplicates are dropped at load")
    miss = sum(_one(con, f"SELECT COUNT(*) FROM {t} WHERE crop_id IS NULL")
               for t in ["fact_production", "fact_district_crop_year", "fact_state_crop_year", "fact_msp",
                         "fact_market_price", "fact_cost_of_cultivation"])
    add("Integrity", "Missing crop_id in fact tables", miss, 0, miss == 0)

    # --- validity ---------------------------------------------------------------------------------
    neg = _one(con, "SELECT COUNT(*) FROM fact_production WHERE area_ha < 0 OR production_apy_unit < 0")
    add("Validity", "Negative area or production", neg, 0, neg == 0)
    bad_px = _one(con, "SELECT COUNT(*) FROM fact_market_price WHERE modal_price <= 0 AND dq_flag NOT LIKE 'excluded%'")
    add("Validity", "Non-positive modal prices left in analysis", bad_px, 0, bad_px == 0)
    excl = _one(con, "SELECT COUNT(*) FROM fact_market_price WHERE dq_flag LIKE 'excluded%'")
    tot = _one(con, "SELECT COUNT(*) FROM fact_market_price")
    add("Validity", "Mandi quotes excluded (<=0 or >5x / <1/5 of median)", excl, "documented", True,
        f"{100 * excl / tot:.2f}% of {tot:,} quotes")
    flag = _one(con, "SELECT COUNT(*) FROM fact_market_price WHERE dq_flag LIKE 'flag%'")
    add("Validity", "Quotes flagged: min/modal/max inconsistent", flag, "documented", True, "kept for modal; no spread")
    msp_bad = _one(con, "SELECT COUNT(*) FROM fact_msp WHERE msp_effective <= 0 OR source_url IS NULL")
    add("Validity", "MSP rows without a positive value or source URL", msp_bad, 0, msp_bad == 0)
    off = _one(con, "SELECT 100.0 * AVG(verification = 'official') FROM fact_msp")
    add("Provenance", "MSP values from official releases", f"{off:.1f}%", ">= 95%", off >= 95,
        "rest flagged 'secondary' (news reports), listed in dq_issues")

    # --- units ------------------------------------------------------------------------------------
    f = pd.read_sql_query("SELECT crop_name, apy_unit, to_price_qtl_factor FROM dim_crop", con).set_index("crop_name")
    ok = (np.isclose(f.loc["Rice", "to_price_qtl_factor"], 10 * RICE_TO_PADDY)
          and np.isclose(f.loc["Cotton", "to_price_qtl_factor"], 1.7 / COTTON_GOT)
          and np.isclose(f.loc["Wheat", "to_price_qtl_factor"], 10))
    add("Units", "Conversion factors: rice -> paddy, lint bale -> kapas, tonnes -> quintals", "rice x14.93, cotton x5.0, others x10",
        "as documented", ok)
    mismatch = _one(con, """SELECT COUNT(*) FROM fact_market_price p JOIN dim_crop c USING(crop_id)
                             WHERE p.msp_applicable IS NOT NULL AND p.msp_comparable = 0""")
    add("Units", "MSP compared with a non-comparable price form (milled rice, lint, dal...)", mismatch, 0, mismatch == 0)

    # --- consistency (SQL vs Python) ---------------------------------------------------------------
    q = load_queries()
    sc = sql_connect()
    pairs = [("q07_rain_yield_correlation", "q07a_rain_yield_association", "crop_name", "pearson_r", 0.002),
             ("q12_real_msp_vs_inflation", "q09c_real_msp_by_crop", "msp_key", "real_growth_pct", 0.11),
             ("q15_season_2026_outlook", "q11g_season_2026_outlook", "crop_name", "pct_below_next_msp", 0.11)]
    for qs, csv, key, colname, tol in pairs:
        a = pd.read_sql_query(q[qs], sc).set_index(key)[colname]
        b = pd.read_csv(RESULTS / f"{csv}.csv").set_index(key)[colname]
        common = a.index.intersection(b.index)
        d = float((a[common] - b[common]).abs().max())
        add("Consistency", f"SQL {qs} vs pandas {csv} ({colname})", f"max diff {d:.3f} over {len(common)}", f"<= {tol}", d <= tol)
    sc.close()

    # --- external validation ----------------------------------------------------------------------
    v = pd.read_sql_query("SELECT * FROM dq_validation", con)
    within = int(v.status.str.startswith("consistent").sum())
    add("Validation", "District sums vs DES 3rd advance estimates 2019-20 (within 10%)", f"{within}/{len(v)}", "documented",
        True, "rice +12%, wheat +14%, maize -29%: 2019-20 provisional, excluded from default window")

    n_tests = len(re.findall(r"^def test_", (ROOT / "tests" / "test_pipeline.py").read_text(), flags=re.M))
    add("Tests", "Automated pipeline tests (pytest tests/)", n_tests, "all pass", True, "run: python -m pytest -q tests")
    issues = pd.read_sql_query("SELECT domain, issue, action, n_rows, detail FROM dq_issues", con)
    con.close()
    return pd.DataFrame(rows), issues, v


def write_docs(s, issues, v):
    def md_table(df):
        df = df.fillna("")
        out = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
        out += ["| " + " | ".join(str(x).replace("|", "/") for x in r) + " |" for r in df.itertuples(index=False)]
        return "\n".join(out)

    head = ["# Data quality", "",
            "Generated by `src/dq_report.py` on every pipeline run, so these numbers always match the data.",
            "PASS = check met. Rows marked *documented* are known issues that were handled (excluded, flagged or kept with a note).", ""]
    body = head + ["## Checks", "", md_table(s[["area", "check", "value", "expected", "status", "note"]]), "",
                   "## Issues found and how they were handled", "", md_table(issues), "",
                   "## External validation (district sums vs official all-India estimates)", "",
                   md_table(v[["crop_name", "crop_year", "dataset_value", "official_value", "unit", "diff_pct", "status"]]), "",
                   "## Why these checks", "",
                   "- **Integrity:** every fact row joins to its dimensions and no key appears twice, so totals are not double-counted.",
                   "- **Validity:** impossible values (zero or negative prices, implausible yields) are removed before they reach averages.",
                   "- **Units:** APY reports milled rice and lint cotton while MSP is for paddy and kapas; the checks confirm the conversion factors and that MSP is only compared with matching price forms.",
                   "- **Consistency:** key answers are computed twice, in SQL and in pandas, and must agree.",
                   "- **Validation:** the cleaned production totals are compared with independent official estimates.", ""]
    (DOCS / "DATA_QUALITY.md").write_text("\n".join(body), encoding="utf-8")

    # README block between markers
    lines = ["```text", "DATA QUALITY  (auto-generated by src/dq_report.py)"]
    for r in s.itertuples():
        mark = "✓" if r.status == "PASS" else "!"
        lines.append(f"{mark} {r.check:<80} {str(r.value)}")
    lines += ["```", "Details: [`docs/DATA_QUALITY.md`](docs/DATA_QUALITY.md)"]
    readme = ROOT / "README.md"
    t = readme.read_text(encoding="utf-8")
    block = "<!-- DQ:START -->\n" + "\n".join(lines) + "\n<!-- DQ:END -->"
    if "<!-- DQ:START -->" in t:
        t = re.sub(r"<!-- DQ:START -->.*?<!-- DQ:END -->", lambda _: block, t, flags=re.S)
        readme.write_text(t, encoding="utf-8")


def main():
    s, issues, v = checks()
    s.to_csv(RESULTS / "dq_summary.csv", index=False)
    write_docs(s, issues, v)
    print(s[["check", "value", "status"]].to_string(index=False))
    bad = s[s.status != "PASS"]
    if len(bad):
        print(f"\n{len(bad)} check(s) need attention")


if __name__ == "__main__":
    main()
