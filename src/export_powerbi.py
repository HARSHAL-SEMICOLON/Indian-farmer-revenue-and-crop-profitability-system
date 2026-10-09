"""Export the star schema from SQLite to CSV for Power BI (power_bi/data/)."""
import sqlite3
import pandas as pd
from .config import DB_PATH, connect_ro, EXPORT, RESULTS

TABLES = ["dim_crop", "dim_state", "dim_location", "dim_year", "dim_market", "dim_date",
          "fact_production", "fact_district_crop_year", "fact_state_crop_year", "fact_msp",
          "fact_market_price", "fact_cost_of_cultivation", "fact_weather_state", "fact_weather_subdivision",
          "dq_issues", "dq_coverage", "dq_validation", "ref_sources"]
# small pre-computed analytic tables useful as Power BI helper tables
RESULT_TABLES = ["q04b_value_growth_decomposition", "q07a_rain_yield_association", "q10a_market_volatility_mh",
                 "q05a_cross_market_dispersion_2024", "q11a_msp_gap_2026", "q11b_msp_gap_by_month_2026",
                 "q11c_dispersion_2026", "q11e_volatility_by_crop_2026", "q11f_daily_median_price_2026",
                 "q11g_season_2026_outlook", "q11h_msp_2026_27_vs_cost"]


def main():
    con = connect_ro()
    for t in TABLES:
        df = pd.read_sql_query(f"SELECT * FROM {t}", con)
        df.to_csv(EXPORT / f"{t}.csv", index=False, encoding="utf-8")
        print(f"{t:28s} {len(df):>8,}")
    for t in RESULT_TABLES:
        pd.read_csv(RESULTS / f"{t}.csv").to_csv(EXPORT / f"agg_{t}.csv", index=False)
    con.close()


if __name__ == "__main__":
    main()
