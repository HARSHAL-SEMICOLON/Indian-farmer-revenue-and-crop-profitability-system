"""
Integrity tests for the database and the methodology rules.
Run:  python -m pytest tests -q      (or simply:  python tests/test_pipeline.py)
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import RICE_TO_PADDY, COTTON_GOT, connect_ro  # noqa: E402
from src.build_prices import msp_crop_year  # noqa: E402

con = connect_ro()


def sql(s):
    return pd.read_sql_query(s, con)


def test_foreign_keys_clean():
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []


def test_no_income_terminology_in_schema():
    cols = sql("SELECT name FROM pragma_table_info('fact_district_crop_year') UNION ALL "
               "SELECT name FROM pragma_table_info('fact_state_crop_year')")["name"]
    assert not any("income" in c.lower() for c in cols)


def test_unit_conversions():
    c = sql("SELECT crop_name, to_price_qtl_factor FROM dim_crop").set_index("crop_name").to_price_qtl_factor
    assert abs(c["Wheat"] - 10) < 1e-9                          # 1 t = 10 qtl
    assert abs(c["Rice"] - 10 * RICE_TO_PADDY) < 1e-9            # milled rice -> paddy
    assert abs(c["Cotton"] - 1.7 / COTTON_GOT) < 1e-9            # lint bale -> kapas qtl
    assert abs(c["Jute"] - 1.8) < 1e-9                           # 180 kg bale


def test_gross_value_equals_quantity_times_msp():
    d = sql("SELECT production_price_qtl, msp_effective, gross_value_msp_inr FROM fact_district_crop_year "
            "WHERE gross_value_msp_inr IS NOT NULL LIMIT 5000")
    assert ((d.production_price_qtl * d.msp_effective - d.gross_value_msp_inr).abs() < 1e-3).all()


def test_valuation_only_inside_window_and_for_msp_crops():
    bad = sql("""SELECT COUNT(*) n FROM fact_district_crop_year f JOIN dim_crop c USING(crop_id)
                 WHERE f.gross_value_msp_inr IS NOT NULL AND (f.crop_year < 2004 OR f.crop_year > 2019 OR c.msp_key IS NULL)""")
    assert bad.n[0] == 0


def test_profit_only_where_official_cost_exists():
    bad = sql("SELECT COUNT(*) n FROM fact_state_crop_year WHERE est_profit_c2_per_ha IS NOT NULL AND c2_per_ha IS NULL")
    assert bad.n[0] == 0
    yrs = sql("SELECT MIN(crop_year) a, MAX(crop_year) b FROM fact_state_crop_year WHERE est_profit_c2_per_ha IS NOT NULL")
    assert yrs.a[0] >= 2008 and yrs.b[0] <= 2013


def test_msp_values_have_sources():
    m = sql("SELECT * FROM fact_msp")
    assert m.source_url.notna().all() and (m.msp_effective > 0).all()
    assert m.duplicated(["msp_key", "crop_year"]).sum() == 0
    # spot checks against official releases
    v = m.set_index(["msp_key", "crop_year"]).msp_effective
    assert v[("Paddy", 2018)] == 1750 and v[("Wheat", 2018)] == 1840 and v[("Cotton", 2024)] == 7121
    assert v[("Gram", 2016)] == 4200          # 4000 + 200 bonus (PIB relid=153642)
    assert v[("Bajra", 2013)] == 1250         # CMO copy error corrected


def test_marketing_season_rule():
    ts = pd.Timestamp
    assert msp_crop_year("Wheat", ts("2015-05-01")) == 2014     # RMS 2015-16
    assert msp_crop_year("Wheat", ts("2015-02-01")) == 2013     # RMS 2014-15
    assert msp_crop_year("Rice", ts("2024-09-30")) == 2023      # KMS 2023-24 still running
    assert msp_crop_year("Rice", ts("2024-10-01")) == 2024


def test_msp_comparison_only_for_comparable_forms():
    bad = sql("SELECT COUNT(*) n FROM fact_market_price WHERE msp_applicable IS NOT NULL AND msp_comparable = 0")
    assert bad.n[0] == 0
    forms = sql("SELECT DISTINCT price_form FROM fact_market_price WHERE msp_applicable IS NOT NULL").price_form
    assert "Milled rice" not in set(forms)


def test_price_sanity():
    p = sql("SELECT * FROM fact_market_price WHERE dq_flag = 'ok'")
    assert (p.min_price <= p.modal_price).all() and (p.modal_price <= p.max_price).all()


def test_rainfall_window():
    m = sql("SELECT MAX(crop_year) y FROM fact_state_crop_year WHERE yield_anomaly_pct IS NOT NULL")
    assert m.y[0] <= 2015


def test_sql_file_matches_python_analytics():
    from src.sql_queries import load_queries, connect
    c = connect()
    q = load_queries()
    assert len(q) == 15  # noqa
    r_sql = pd.read_sql_query(q["q07_rain_yield_correlation"], c).set_index("crop_name").pearson_r
    r_py = pd.read_csv(ROOT / "outputs" / "results" / "q07a_rain_yield_association.csv").set_index("crop_name").pearson_r
    common = r_sql.index.intersection(r_py.index)
    assert len(common) > 10 and (r_sql[common] - r_py[common]).abs().max() < 0.002
    v = pd.read_sql_query(q["q09_value_over_time"], c).set_index("crop_year")
    assert v.loc[2018, "nominal_index"] > v.loc[2018, "real_index"] > v.loc[2018, "volume_index"]
    # real MSP growth: SQL (q12) == pandas (q09c)
    a = pd.read_sql_query(q["q12_real_msp_vs_inflation"], c).set_index("msp_key").real_growth_pct
    b = pd.read_csv(ROOT / "outputs" / "results" / "q09c_real_msp_by_crop.csv").set_index("msp_key").real_growth_pct
    assert len(a) == len(b) == 20 and (a - b[a.index]).abs().max() <= 0.11
    # 2026 outlook: SQL (q15) == pandas (q11g)
    a = pd.read_sql_query(q["q15_season_2026_outlook"], c).set_index("crop_name").pct_below_next_msp
    b = pd.read_csv(ROOT / "outputs" / "results" / "q11g_season_2026_outlook.csv").set_index("crop_name").pct_below_next_msp
    assert set(a.index) == set(b.index) and (a - b[a.index]).abs().max() <= 0.11


def test_recent_mandi_data_loaded():
    m = sql("""SELECT MIN(d.price_date) a, MAX(d.price_date) b, COUNT(*) n FROM fact_market_price p
               JOIN dim_date d USING(date_key) WHERE p.source_dataset = 'AGMARKNET daily Jul-Sep 2026'""")
    assert m.n[0] > 50000 and m.b[0] >= "2026-09-01"
    # kharif crops sold Jul-Sep 2026 use KMS 2025-26; rabi crops use RMS 2026-27 (both crop year 2025)
    y = sql("""SELECT DISTINCT msp_crop_year FROM fact_market_price
               WHERE source_dataset = 'AGMARKNET daily Jul-Sep 2026' AND msp_applicable IS NOT NULL""")
    assert set(y.msp_crop_year.astype(int)) == {2025}


if __name__ == "__main__":
    fns = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    failed = 0
    for f in fns:
        try:
            f()
            print("PASS", f.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL", f.__name__, e)
    print(f"{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)


def test_msp_2026_season_loaded():
    """KMS 2026-27 (PIB 13-May-2026) and RMS 2027-28 (30-Sep-2026) are stored as crop year 2026."""
    con = connect_ro()
    m = pd.read_sql_query("SELECT msp_key, msp_effective FROM fact_msp WHERE crop_year = 2026", con)
    con.close()
    v = dict(zip(m.msp_key, m.msp_effective))
    assert len(v) == 20
    assert v["Paddy"] == 2441 and v["Cotton"] == 8267 and v["Wheat"] == 2610 and v["Mustard"] == 6613


def test_supplementary_apy_loader_checks_units():
    """A newer DES export (different headers, '2020-21' years, unit column) maps onto the base format;
    rows whose production unit doesn't match the crop's APY unit are rejected."""
    from src.build_production import normalize_apy
    from src.config import CROPS, CROP_COLS
    crops = pd.DataFrame(CROPS, columns=CROP_COLS)
    df = pd.DataFrame({"State": ["Punjab", "Gujarat", "Kerala"], "District": ["Ludhiana", "Rajkot", "Kozhikode"],
                       "Crop": ["Rice", "Cotton", "Rice"], "Year": ["2020-21", "2020-21", "2021-22"],
                       "Season": ["Kharif", "Kharif", "Kharif"], "Area": ["2,50,000", "1000", "500"],
                       "Production": [1000000, 4000, 1200], "Production Units": ["Tonnes", "Bales", "Nuts"]})
    out, bad = normalize_apy(df, crops)
    assert list(out.year) == [2020, 2020] and list(out.crop) == ["Rice", "Cotton(Lint)"]
    assert out.area.iloc[0] == 250000 and len(bad) == 1
