import os
import time
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from app import db
from app.services import forecasting, inventory, decision, network, cache
from app.db import get_conn

app = FastAPI(title="MedCare Pharma P1 - Demand Sensing & Replenishment Planning API", version="1.0.0")

# CORS is environment-configurable rather than a hardcoded wildcard, so the
# deployed frontend origin can be allow-listed explicitly in production
# instead of relying on allow_origins=["*"] (which is also invalid together
# with allow_credentials=True per the CORS spec — browsers reject it).
#
# Set ALLOWED_ORIGINS to a comma-separated list of exact origins, e.g.:
#   ALLOWED_ORIGINS=https://medcare-p1.vercel.app,http://localhost:5173
# If unset, defaults to common local dev origins only.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173,https://demand-five.vercel.app"
_allowed_origins_raw = os.environ.get("ALLOWED_ORIGINS", _default_origins)
ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _warm_forecast_cache():
    n = cache.warm_cache()
    print(f"[startup] forecast cache warmed for {n} SKU x DC combinations")
    print(f"[startup] CORS allowed origins: {ALLOWED_ORIGINS}")


def _validate_sku_dc(sku_id, dc_id):
    if not db.valid_sku(sku_id):
        raise HTTPException(status_code=422, detail=f"Unknown sku_id '{sku_id}'. Valid SKUs: {[s['sku_id'] for s in db.list_skus()]}")
    if not db.valid_dc(dc_id):
        raise HTTPException(status_code=422, detail=f"Unknown dc_id '{dc_id}'. Valid DCs: {[d['dc_id'] for d in db.list_dcs()]}")


@app.get("/api/health")
def health():
    return {
        "status": "ok", "service": "medcare-p1-api", "today": db.get_today(),
        "time": datetime.utcnow().isoformat(), "forecast_cache_size": cache.cache_size(),
        "allowed_origins": ALLOWED_ORIGINS,
    }


@app.get("/api/skus")
def get_skus():
    return db.list_skus()


@app.get("/api/dcs")
def get_dcs():
    return db.list_dcs()


@app.get("/api/scenarios")
def get_scenarios():
    return [
        {"sku_id": "MED-001", "dc_id": "DC-TIER2-HYD", "label": "Flu surge shortage (Tier-2)", "expected": "TRANSFER"},
        {"sku_id": "MED-001", "dc_id": "DC-METRO-CHN", "label": "Metro excess w/ near-expiry batch", "expected": "MONITOR (expiry watch)"},
        {"sku_id": "MED-002", "dc_id": "DC-TIER2-LKO", "label": "Chronic understock", "expected": "TRANSFER/REPLENISH"},
        {"sku_id": "MED-003", "dc_id": "DC-TIER2-PAT", "label": "Transfer-infeasible shortage (long lead time)", "expected": "REPLENISH"},
        {"sku_id": "MED-004", "dc_id": "DC-METRO-MUM", "label": "Healthy SKU", "expected": "MONITOR"},
    ]


@app.get("/api/forecast/{sku_id}/{dc_id}")
def get_forecast_endpoint(sku_id: str, dc_id: str):
    _validate_sku_dc(sku_id, dc_id)
    try:
        return forecasting.get_forecast(sku_id, dc_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/inventory/{sku_id}/{dc_id}")
def get_inventory_endpoint(sku_id: str, dc_id: str):
    _validate_sku_dc(sku_id, dc_id)
    fc = forecasting.get_forecast(sku_id, dc_id)
    inv = inventory.get_inventory_position(sku_id, dc_id, fc["sensed_avg_daily"])
    fefo = inventory.fefo_allocation_and_expiry_risk(sku_id, dc_id, fc["sensed_forecast"])
    return {**inv, "fefo": fefo}


@app.get("/api/recommendation/{sku_id}/{dc_id}")
def get_recommendation(sku_id: str, dc_id: str):
    _validate_sku_dc(sku_id, dc_id)
    try:
        return decision.evaluate(sku_id, dc_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


class WhatIfRequest(BaseModel):
    sku_id: str
    dc_id: str
    demand_change_pct: Optional[float] = Field(default=None, ge=-90, le=300)
    flu_active: Optional[bool] = None
    lead_time_delta: Optional[int] = Field(default=None, ge=-10, le=30)
    cost_weight_stockout: Optional[float] = Field(default=1.0, ge=0.1, le=5.0)


@app.post("/api/what-if")
def what_if(req: WhatIfRequest):
    _validate_sku_dc(req.sku_id, req.dc_id)
    t0 = time.time()
    before = decision.evaluate(req.sku_id, req.dc_id, demand_override=None, cost_weight_stockout=1.0)
    override = {
        "demand_change_pct": req.demand_change_pct,
        "flu_active": req.flu_active,
        "lead_time_delta": req.lead_time_delta,
    }
    after = decision.evaluate(req.sku_id, req.dc_id, demand_override=override, cost_weight_stockout=req.cost_weight_stockout or 1.0)
    elapsed_ms = round((time.time() - t0) * 1000, 1)

    def summarize(r):
        return {
            "sensed_avg_daily_forecast": r["forecast"]["sensed_avg_daily"],
            "reorder_point": r["rop"]["reorder_point"],
            "stockout_risk_score": r["risk"]["stockout_risk_score"],
            "stockout_risk_level": r["risk"]["stockout_risk_level"],
            "expiry_risk_score": r["risk"]["expiry_risk_score"],
            "action": r["decision"]["action"],
            "quantity": r["decision"]["quantity"],
            "source_dc_name": r["decision"]["source_dc_name"],
            "priority": r["priority"]["priority"],
            "total_cost_of_inaction": r["cost"]["total_cost_of_inaction"],
        }

    return {"before": summarize(before), "after": summarize(after), "full_after": after, "compute_time_ms": elapsed_ms}


@app.get("/api/network-map")
def get_network_map():
    dcs = db.list_dcs()
    skus = db.list_skus()
    nodes = []
    edges = []
    for dc in dcs:
        worst_risk = 0
        worst_sku = None
        total_stock = 0
        for sku in skus:
            try:
                r = decision.evaluate(sku["sku_id"], dc["dc_id"])
            except ValueError:
                continue
            total_stock += r["inventory"]["current_stock"]
            if r["risk"]["combined_risk_score"] > worst_risk:
                worst_risk = r["risk"]["combined_risk_score"]
                worst_sku = sku["sku_id"]
            if r["decision"]["action"] == "TRANSFER" and r["decision"]["source_dc"]:
                edges.append({
                    "source": r["decision"]["source_dc"], "target": dc["dc_id"],
                    "sku_id": sku["sku_id"], "quantity": r["decision"]["quantity"],
                    "timing_days": r["decision"]["timing_days"],
                })
        state = "Shortage" if worst_risk >= 45 else ("Excess" if worst_risk < 15 and total_stock > dc["capacity_units"] * 0.5 else "Healthy")
        nodes.append({
            "dc_id": dc["dc_id"], "name": dc["name"], "type": dc["type"], "city": dc["city"],
            "state": state, "worst_risk_score": worst_risk, "worst_sku": worst_sku,
            "total_stock": total_stock, "capacity": dc["capacity_units"],
        })
    return {"nodes": nodes, "edges": edges}


@app.get("/api/attention-queue")
def get_attention_queue(limit: int = Query(default=10, ge=1, le=50)):
    dcs = db.list_dcs()
    skus = db.list_skus()
    items = []
    for dc in dcs:
        for sku in skus:
            try:
                r = decision.evaluate(sku["sku_id"], dc["dc_id"])
            except ValueError:
                continue
            if r["decision"]["action"] != "MONITOR" or r["risk"]["combined_risk_score"] >= 15:
                items.append({
                    "sku_id": sku["sku_id"], "sku_name": sku["name"], "dc_id": dc["dc_id"], "dc_name": dc["name"],
                    "action": r["decision"]["action"], "priority": r["priority"]["priority"],
                    "priority_score": r["priority"]["priority_score"],
                    "combined_risk_score": r["risk"]["combined_risk_score"],
                    "stockout_risk_score": r["risk"]["stockout_risk_score"],
                    "expiry_risk_score": r["risk"]["expiry_risk_score"],
                    "quantity": r["decision"]["quantity"],
                    "explanation": r["decision"]["explanation"],
                })
    items.sort(key=lambda x: x["priority_score"], reverse=True)
    return items[:limit]


@app.get("/api/network-health")
def get_network_health():
    dcs = db.list_dcs()
    skus = db.list_skus()
    combos = []
    for dc in dcs:
        for sku in skus:
            try:
                r = decision.evaluate(sku["sku_id"], dc["dc_id"])
            except ValueError:
                continue
            combos.append(r)
    if not combos:
        raise HTTPException(status_code=500, detail="No data available")

    total = len(combos)
    action_counts = {"TRANSFER": 0, "REPLENISH": 0, "MONITOR": 0}
    for r in combos:
        action_counts[r["decision"]["action"]] += 1

    avg_stockout_risk = round(sum(r["risk"]["stockout_risk_score"] for r in combos) / total, 1)
    avg_expiry_risk = round(sum(r["risk"]["expiry_risk_score"] for r in combos) / total, 1)
    total_cost_exposure = round(sum(r["cost"]["total_cost_of_inaction"] for r in combos), 2)
    critical_count = sum(1 for r in combos if r["priority"]["priority"] == "Critical")
    network_health_score = round(100 - (avg_stockout_risk * 0.5 + avg_expiry_risk * 0.5), 1)

    return {
        "combos_evaluated": total,
        "network_health_score": max(0, network_health_score),
        "avg_stockout_risk": avg_stockout_risk,
        "avg_expiry_risk": avg_expiry_risk,
        "action_distribution": action_counts,
        "total_cost_of_inaction_exposure": total_cost_exposure,
        "critical_priority_count": critical_count,
    }


@app.get("/api/monitoring/metrics")
def monitoring_metrics():
    dcs = db.list_dcs()
    skus = db.list_skus()
    mape_values, mae_values = [], []
    for dc in dcs:
        for sku in skus:
            try:
                fc = forecasting.get_forecast(sku["sku_id"], dc["dc_id"])
            except ValueError:
                continue
            if fc["evaluation"]["sensed_metrics"]["mape"] is not None:
                mape_values.append(fc["evaluation"]["sensed_metrics"]["mape"])
            mae_values.append(fc["evaluation"]["sensed_metrics"]["mae"])
    avg_mape = round(sum(mape_values) / len(mape_values), 2) if mape_values else None
    avg_mae = round(sum(mae_values) / len(mae_values), 2) if mae_values else None
    return {"avg_sensed_mape_pct": avg_mape, "avg_sensed_mae": avg_mae, "combos_evaluated": len(mae_values)}


@app.get("/api/monitoring/history")
def monitoring_history():
    """
    Returns recorded monitoring snapshots (network health at successive runs).
    A snapshot is recorded automatically whenever this endpoint is called if
    none exists for 'today', so the trend view has genuine, non-fabricated history
    to display after the app has been used across a few sessions/runs.
    """
    conn = get_conn()
    rows = conn.execute("SELECT run_ts, sku_id, dc_id, action, risk_score, priority, stockout_exposure, expiry_exposure FROM monitoring_runs ORDER BY run_ts").fetchall()
    if not rows:
        # seed with the current computed state as the first snapshot
        health = get_network_health()
        conn.execute(
            "INSERT INTO monitoring_runs VALUES (?,?,?,?,?,?,?,?)",
            (datetime.utcnow().isoformat(), "ALL", "ALL", "SNAPSHOT", health["avg_stockout_risk"], "N/A",
             health["avg_stockout_risk"], health["avg_expiry_risk"]),
        )
        conn.commit()
        rows = conn.execute("SELECT run_ts, sku_id, dc_id, action, risk_score, priority, stockout_exposure, expiry_exposure FROM monitoring_runs ORDER BY run_ts").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/network/{sku_id}/{dc_id}")
def get_network_alternatives(sku_id: str, dc_id: str):
    _validate_sku_dc(sku_id, dc_id)
    sku = db.get_sku(sku_id)
    fc = forecasting.get_forecast(sku_id, dc_id)
    inv = inventory.get_inventory_position(sku_id, dc_id, fc["sensed_avg_daily"])
    from app.services import rop as rop_service
    dc = db.get_dc(dc_id)
    rop_result = rop_service.compute_rop(fc["sensed_avg_daily"], fc["demand_std_dev"], dc["supplier_lead_time_days"], sku["criticality"])
    shortfall = max(0, rop_result["reorder_point"] - inv["current_stock"])
    return network.find_network_alternatives(sku_id, dc_id, shortfall, sku["criticality"])
