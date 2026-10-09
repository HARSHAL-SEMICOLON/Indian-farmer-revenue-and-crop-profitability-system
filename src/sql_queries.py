"""
Run every query in sql/analysis_queries.sql and save results to outputs/results/sql_<name>.csv.
Usage:  python -m src.sql_queries
"""
import math
import re

import pandas as pd

from .config import RESULTS, SQL_DIR, connect_ro


def load_queries(path=SQL_DIR / "analysis_queries.sql"):
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^-- name: (\S+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def connect():
    con = connect_ro()
    try:
        con.execute("SELECT SQRT(4)")
    except Exception:  # older SQLite builds lack math functions
        con.create_function("SQRT", 1, lambda x: None if x is None or x < 0 else math.sqrt(x), deterministic=True)
        con.create_function("LN", 1, lambda x: None if x is None or x <= 0 else math.log(x), deterministic=True)
    return con


def main():
    con = connect()
    out = {}
    for name, sql in load_queries().items():
        df = pd.read_sql_query(sql, con)
        df.to_csv(RESULTS / f"sql_{name}.csv", index=False)
        out[name] = df
        print(f"{name:42s} {len(df):>5} rows")
    con.close()
    return out


if __name__ == "__main__":
    main()
