import sqlite3
import os
import pandas as pd

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "medcare.db"))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(sql, params=()):
    conn = get_conn()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def get_today():
    conn = get_conn()
    row = conn.execute("SELECT value FROM meta WHERE key='today'").fetchone()
    conn.close()
    return row["value"] if row else None


def list_skus():
    return query_df("SELECT * FROM skus").to_dict("records")


def list_dcs():
    return query_df("SELECT * FROM dcs").to_dict("records")


def get_sku(sku_id):
    df = query_df("SELECT * FROM skus WHERE sku_id = ?", (sku_id,))
    return df.to_dict("records")[0] if len(df) else None


def get_dc(dc_id):
    df = query_df("SELECT * FROM dcs WHERE dc_id = ?", (dc_id,))
    return df.to_dict("records")[0] if len(df) else None


def valid_sku(sku_id):
    return sku_id in [s["sku_id"] for s in list_skus()]


def valid_dc(dc_id):
    return dc_id in [d["dc_id"] for d in list_dcs()]
