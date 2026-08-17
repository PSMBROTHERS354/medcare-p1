"""
Forecast cache.

Holt-Winters fitting is not free -- re-fitting it for all 30 SKU x DC combinations
on every network-wide request (network health, attention queue, network map) would
make the UI feel sluggish. So forecasts are computed once (offline / on startup)
and served from an in-memory + SQLite-persisted cache for anything that doesn't
need a live "what-if" override. What-if requests always compute live (a single
SKU/DC fit is fast, ~50-150ms) since they need fresh numbers for the exact
scenario the user is exploring.
"""
import json
from datetime import datetime, timezone
from app.db import list_skus, list_dcs, get_conn
from app.services import forecasting

_CACHE = {}


def warm_cache():
    conn = get_conn()
    computed = 0
    for sku in list_skus():
        for dc in list_dcs():
            key = (sku["sku_id"], dc["dc_id"])
            try:
                fc = forecasting.get_forecast(sku["sku_id"], dc["dc_id"])
            except ValueError:
                continue
            _CACHE[key] = fc
            conn.execute(
                "INSERT OR REPLACE INTO forecast_cache VALUES (?,?,?,?)",
                (sku["sku_id"], dc["dc_id"], datetime.now(timezone.utc).isoformat(), json.dumps(fc)),
            )
            computed += 1
    conn.commit()
    conn.close()
    return computed


def get_cached_forecast(sku_id, dc_id):
    key = (sku_id, dc_id)
    if key in _CACHE:
        return _CACHE[key]
    # fall back to persisted cache, then live compute (and populate cache)
    conn = get_conn()
    row = conn.execute("SELECT payload FROM forecast_cache WHERE sku_id=? AND dc_id=?", (sku_id, dc_id)).fetchone()
    conn.close()
    if row:
        fc = json.loads(row["payload"])
        _CACHE[key] = fc
        return fc
    fc = forecasting.get_forecast(sku_id, dc_id)
    _CACHE[key] = fc
    return fc


def cache_size():
    return len(_CACHE)
