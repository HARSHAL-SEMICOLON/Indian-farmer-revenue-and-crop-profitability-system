"""
Run the full pipeline end to end:   python run_pipeline.py

raw data -> curated MSP -> dimensions & facts -> SQLite star schema -> analytics -> Power BI CSVs
The notebooks in notebooks/ walk through the same steps one by one with explanations and charts.
"""
import time

from src import (build_msp, build_production, build_prices, build_costs_weather, build_economics,
                 build_quality, load_db, analytics, sql_queries, dq_report, data_dictionary, export_powerbi)

STEPS = [
    ("MSP (official, curated)", build_msp.main),
    ("production + dimensions", build_production.main),
    ("mandi prices", build_prices.main),
    ("cost of cultivation", build_costs_weather.build_costs),
    ("rainfall", build_costs_weather.build_weather),
    ("crop economics", build_economics.main),
    ("data quality", build_quality.main),
    ("SQLite database", load_db.main),
    ("analytics (10 questions)", analytics.main),
    ("SQL analysis queries", sql_queries.main),
    ("data-quality report", dq_report.main),
    ("data dictionary", data_dictionary.main),
    ("Power BI export", export_powerbi.main),
]

if __name__ == "__main__":
    t = time.time()
    for name, fn in STEPS:
        print(f"\n== {name} ==")
        fn()
    print(f"\nDone in {time.time() - t:.1f}s")
