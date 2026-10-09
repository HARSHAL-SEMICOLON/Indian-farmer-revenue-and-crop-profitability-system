"""Create the SQLite database from schema.sql and load all processed tables."""
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
from .config import cpi_deflator_2018, PROC, CURATED, DB_PATH, SQL_DIR

TABLES = {
    "dim_crop": PROC / "dim_crop.csv", "dim_state": PROC / "dim_state.csv",
    "dim_location": PROC / "dim_location.csv", "dim_year": PROC / "dim_year.csv",
    "dim_market": PROC / "dim_market.csv", "dim_date": PROC / "dim_date.csv",
    "fact_production": PROC / "fact_production.csv",
    "fact_district_crop_year": PROC / "fact_district_crop_year.csv",
    "fact_state_crop_year": PROC / "fact_state_crop_year.csv",
    "fact_msp": CURATED / "msp_official_curated.csv",
    "fact_market_price": PROC / "fact_market_price.csv",
    "fact_cost_of_cultivation": PROC / "fact_cost_of_cultivation.csv",
    "fact_weather_subdivision": PROC / "fact_weather_subdivision.csv",
    "fact_weather_state": PROC / "fact_weather_state.csv",
    "dq_issues": PROC / "dq_issues.csv", "dq_coverage": PROC / "dq_coverage.csv",
    "dq_validation": PROC / "dq_validation.csv", "ref_sources": PROC / "ref_sources.csv",
}


def main():
    # Build in a local temp dir, then copy: SQLite locking fails on some network/VM-mounted folders.
    tmp = Path(tempfile.mkdtemp()) / DB_PATH.name
    con = sqlite3.connect(tmp)
    con.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
    crop = pd.read_csv(PROC / "dim_crop.csv")
    for table, path in TABLES.items():
        df = pd.read_csv(path, low_memory=False)
        if table == "fact_msp":
            df = df.merge(crop[["crop_id", "msp_key"]], on="msp_key", how="left")
            df.insert(0, "msp_id", range(1, len(df) + 1))
            df["msp_real_2018"] = df["msp_effective"] / df["crop_year"].map(cpi_deflator_2018()) * 100
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        df = df[[c for c in cols if c in df.columns]]
        for c in df.columns:
            if df[c].dtype == bool:
                df[c] = df[c].astype(int)
        if table == "dim_date":
            df["price_date"] = df["price_date"].astype(str)
        df.to_sql(table, con, if_exists="append", index=False, chunksize=20000)
        print(f"{table:28s} {len(df):>8,}")
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    print("foreign key violations:", len(fk))
    con.execute("VACUUM")
    con.close()
    shutil.copyfile(tmp, DB_PATH)
    shutil.rmtree(tmp.parent, ignore_errors=True)
    print("database written to", DB_PATH)


if __name__ == "__main__":
    main()
