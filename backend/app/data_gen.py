"""
Synthetic data generator for MedCare Pharma P1 (Demand Sensing & Replenishment Planning).

Deterministic (seeded) generation. Deliberately engineers the following business
scenarios so the downstream engine has real material to reason over:

  SKU-DC combo              | Engineered condition
  ---------------------------|----------------------------------------------
  MED-001 @ DC-TIER2-HYD     | Flu-driven demand surge, low stock -> shortage
  MED-001 @ DC-METRO-CHN     | Metro excess, near-expiry batches -> transfer source
  MED-002 @ DC-TIER2-LKO     | Chronic understock (structurally low stock, no flu)
  MED-003 @ DC-TIER2-PAT     | Transfer-infeasible shortage (long lead time / no source)
  MED-004 @ DC-METRO-MUM     | Healthy SKU, balanced -> MONITOR
  MED-005 (all DCs)          | Near-expiry excess emphasis, FEFO demonstration
  MED-006 (all DCs)          | Low criticality, general background noise

Nothing about final recommendations (TRANSFER/REPLENISH/MONITOR) is hardcoded here -
only the raw inputs (demand, stock, expiry, lead time, capacity) are engineered.
The decision engine computes outputs independently from this data.
"""
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

SEED = 42
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "medcare.db")
DB_PATH = os.path.abspath(DB_PATH)

HISTORY_DAYS = 180
TODAY = datetime(2026, 8, 16)
START_DATE = TODAY - timedelta(days=HISTORY_DAYS)

SKUS = [
    # sku_id, name, category, criticality, unit_cost, margin_per_unit, shelf_life_days
    ("MED-001", "Amoxicillin 500mg", "Antibiotic", "Critical", 12.0, 6.0, 365),
    ("MED-002", "Paracetamol 650mg", "Analgesic", "High", 3.5, 1.5, 730),
    ("MED-003", "Insulin Glargine", "Chronic Care", "Critical", 45.0, 18.0, 270),
    ("MED-004", "Cetirizine 10mg", "Antihistamine", "Medium", 2.0, 0.8, 900),
    ("MED-005", "Azithromycin 250mg", "Antibiotic", "High", 15.0, 6.5, 240),
    ("MED-006", "Multivitamin Syrup", "Supplement", "Low", 4.5, 1.2, 545),
]

DCS = [
    # dc_id, name, type, city, capacity_units
    ("DC-METRO-MUM", "Mumbai Metro DC", "Metro", "Mumbai", 60000),
    ("DC-METRO-CHN", "Chennai Metro DC", "Metro", "Chennai", 55000),
    ("DC-TIER2-HYD", "Hyderabad Tier-2 DC", "Tier-2", "Hyderabad", 18000),
    ("DC-TIER2-LKO", "Lucknow Tier-2 DC", "Tier-2", "Lucknow", 15000),
    ("DC-TIER2-PAT", "Patna Tier-2 DC", "Tier-2", "Patna", 12000),
]

# Inbound replenishment lead time (supplier -> DC), in days, per DC
SUPPLIER_LEAD_TIME = {
    "DC-METRO-MUM": 3,
    "DC-METRO-CHN": 3,
    "DC-TIER2-HYD": 6,
    "DC-TIER2-LKO": 7,
    "DC-TIER2-PAT": 9,  # deliberately long -> supports transfer-infeasible / replenish scenarios
}

# Inter-DC transfer lead time matrix (days). Asymmetric, distance-driven.
TRANSFER_LEAD_TIME = {
    ("DC-METRO-MUM", "DC-METRO-CHN"): 2,
    ("DC-METRO-CHN", "DC-METRO-MUM"): 2,
    ("DC-METRO-MUM", "DC-TIER2-HYD"): 2,
    ("DC-TIER2-HYD", "DC-METRO-MUM"): 2,
    ("DC-METRO-CHN", "DC-TIER2-HYD"): 1,
    ("DC-TIER2-HYD", "DC-METRO-CHN"): 1,
    ("DC-METRO-MUM", "DC-TIER2-LKO"): 3,
    ("DC-TIER2-LKO", "DC-METRO-MUM"): 3,
    ("DC-METRO-CHN", "DC-TIER2-LKO"): 4,
    ("DC-TIER2-LKO", "DC-METRO-CHN"): 4,
    ("DC-METRO-MUM", "DC-TIER2-PAT"): 5,   # deliberately long -> infeasible transfer
    ("DC-TIER2-PAT", "DC-METRO-MUM"): 5,
    ("DC-METRO-CHN", "DC-TIER2-PAT"): 6,   # deliberately long -> infeasible transfer
    ("DC-TIER2-PAT", "DC-METRO-CHN"): 6,
    ("DC-TIER2-HYD", "DC-TIER2-LKO"): 4,
    ("DC-TIER2-LKO", "DC-TIER2-HYD"): 4,
    ("DC-TIER2-HYD", "DC-TIER2-PAT"): 5,
    ("DC-TIER2-PAT", "DC-TIER2-HYD"): 5,
    ("DC-TIER2-LKO", "DC-TIER2-PAT"): 3,
    ("DC-TIER2-PAT", "DC-TIER2-LKO"): 3,
}

# Flu season window (deliberately overlaps recent history + persists as an "active" signal today)
FLU_START = TODAY - timedelta(days=21)
FLU_END = TODAY + timedelta(days=30)
FLU_AFFECTED_DCS = {"DC-TIER2-HYD", "DC-TIER2-PAT", "DC-TIER2-LKO"}  # flu hits Tier-2 hardest
FLU_AFFECTED_SKUS = {"MED-001", "MED-003", "MED-005"}
FLU_BASE_UPLIFT = 0.60  # +60% signal referenced in the problem statement

# Promotion windows: (sku, dc, start_offset_days_from_start, duration_days, uplift)
PROMOTIONS = [
    ("MED-002", "DC-METRO-MUM", 40, 14, 0.35),
    ("MED-004", "DC-METRO-CHN", 90, 10, 0.25),
    ("MED-006", "DC-TIER2-LKO", 130, 7, 0.20),
]

BASE_DAILY_DEMAND = {
    ("MED-001", "DC-METRO-MUM"): 140, ("MED-001", "DC-METRO-CHN"): 150,
    ("MED-001", "DC-TIER2-HYD"): 55, ("MED-001", "DC-TIER2-LKO"): 40, ("MED-001", "DC-TIER2-PAT"): 30,

    ("MED-002", "DC-METRO-MUM"): 300, ("MED-002", "DC-METRO-CHN"): 280,
    ("MED-002", "DC-TIER2-HYD"): 95, ("MED-002", "DC-TIER2-LKO"): 60, ("MED-002", "DC-TIER2-PAT"): 55,

    ("MED-003", "DC-METRO-MUM"): 60, ("MED-003", "DC-METRO-CHN"): 50,
    ("MED-003", "DC-TIER2-HYD"): 22, ("MED-003", "DC-TIER2-LKO"): 18, ("MED-003", "DC-TIER2-PAT"): 15,

    ("MED-004", "DC-METRO-MUM"): 180, ("MED-004", "DC-METRO-CHN"): 170,
    ("MED-004", "DC-TIER2-HYD"): 70, ("MED-004", "DC-TIER2-LKO"): 55, ("MED-004", "DC-TIER2-PAT"): 45,

    ("MED-005", "DC-METRO-MUM"): 90, ("MED-005", "DC-METRO-CHN"): 85,
    ("MED-005", "DC-TIER2-HYD"): 34, ("MED-005", "DC-TIER2-LKO"): 26, ("MED-005", "DC-TIER2-PAT"): 20,

    ("MED-006", "DC-METRO-MUM"): 110, ("MED-006", "DC-METRO-CHN"): 100,
    ("MED-006", "DC-TIER2-HYD"): 40, ("MED-006", "DC-TIER2-LKO"): 32, ("MED-006", "DC-TIER2-PAT"): 25,
}

CRITICALITY_MAP = {s[0]: s[3] for s in SKUS}


def _rng_for(sku, dc):
    """Deterministic per-combo RNG so regeneration is reproducible but varied."""
    seed = (hash((sku, dc, SEED)) % (2**32 - 1))
    return np.random.default_rng(seed)


def _is_promo_active(sku, dc, day_offset):
    for p_sku, p_dc, start, dur, uplift in PROMOTIONS:
        if p_sku == sku and p_dc == dc and start <= day_offset < start + dur:
            return True, uplift
    return False, 0.0


def _flu_multiplier(sku, dc, current_date):
    if sku in FLU_AFFECTED_SKUS and dc in FLU_AFFECTED_DCS and FLU_START <= current_date <= FLU_END:
        # ramps up then holds, not a step function -- more realistic sensing target
        days_in = (current_date - FLU_START).days
        ramp = min(1.0, days_in / 10.0)
        return 1.0 + FLU_BASE_UPLIFT * ramp
    return 1.0


def generate_demand_history():
    rows = []
    for sku_id, *_ in SKUS:
        for dc_id, *_ in DCS:
            base = BASE_DAILY_DEMAND[(sku_id, dc_id)]
            rng = _rng_for(sku_id, dc_id)
            # chronic understock scenario: MED-002 @ DC-TIER2-LKO gets a structural downward drift
            chronic = (sku_id == "MED-002" and dc_id == "DC-TIER2-LKO")
            for day_offset in range(HISTORY_DAYS + 14):  # + 14 days into "future" for holdout/what-if realism? no - keep to history only
                if day_offset >= HISTORY_DAYS:
                    break
                current_date = START_DATE + timedelta(days=day_offset)
                dow = current_date.weekday()
                weekly_season = 1.0 + (0.08 if dow in (0, 4) else (-0.05 if dow == 6 else 0.0))
                promo_active, promo_uplift = _is_promo_active(sku_id, dc_id, day_offset)
                flu_mult = _flu_multiplier(sku_id, dc_id, current_date)
                trend = 1.0
                if chronic:
                    trend = 1.0 - min(0.35, day_offset / HISTORY_DAYS * 0.35)
                noise = rng.normal(1.0, 0.07)
                demand = base * weekly_season * (1 + promo_uplift if promo_active else 1) * flu_mult * trend * noise
                demand = max(0, round(demand))
                # distributor order pattern: batch-like ordering noise (orders placed every ~5 days in larger lots)
                distributor_order = round(demand * rng.uniform(0.9, 1.15)) if day_offset % 5 == 0 else 0
                rows.append({
                    "sku_id": sku_id, "dc_id": dc_id, "date": current_date.strftime("%Y-%m-%d"),
                    "actual_demand": int(demand), "promo_active": int(promo_active),
                    "flu_signal": round(flu_mult - 1.0, 3), "distributor_order_qty": int(distributor_order),
                })
    return pd.DataFrame(rows)


def generate_batches():
    """Batch-level inventory with expiry dates, engineered per scenario."""
    rows = []
    batch_seq = 1
    for sku_id, name, cat, crit, unit_cost, margin, shelf_life in SKUS:
        for dc_id, dc_name, dc_type, city, cap in DCS:
            rng = _rng_for(sku_id + "B", dc_id)
            avg_daily = BASE_DAILY_DEMAND[(sku_id, dc_id)]

            # Determine scenario-driven stock posture
            if sku_id == "MED-001" and dc_id == "DC-TIER2-HYD":
                days_cover_target = 4          # low stock -> flu shortage
                near_expiry_bias = 0.05
            elif sku_id == "MED-001" and dc_id == "DC-METRO-CHN":
                days_cover_target = 32         # metro excess
                near_expiry_bias = 0.55        # lots of near-expiry excess -> transfer source
            elif sku_id == "MED-002" and dc_id == "DC-TIER2-LKO":
                days_cover_target = 3          # chronic understock
                near_expiry_bias = 0.05
            elif sku_id == "MED-003" and dc_id == "DC-TIER2-PAT":
                days_cover_target = 5          # shortage, but isolated (transfer infeasible)
                near_expiry_bias = 0.05
            elif sku_id == "MED-004" and dc_id == "DC-METRO-MUM":
                days_cover_target = 16         # healthy / balanced
                near_expiry_bias = 0.10
            elif sku_id == "MED-005":
                days_cover_target = 20
                near_expiry_bias = 0.40        # near-expiry demonstration across DCs
            else:
                days_cover_target = float(rng.uniform(10, 18))
                near_expiry_bias = float(rng.uniform(0.05, 0.15))

            total_qty = int(avg_daily * days_cover_target)
            total_qty = max(total_qty, 0)
            n_batches = rng.integers(3, 7)
            remaining = total_qty

            # Engineered near-expiry-excess scenario: MED-001 @ Chennai (metro excess) gets
            # one deliberately oversized batch expiring soon -- too large for FEFO to clear
            # against realistic demand before it expires, producing a genuine expiry-risk signal.
            forced_near_expiry_batch = (sku_id == "MED-001" and dc_id == "DC-METRO-CHN")

            for b in range(n_batches):
                if remaining <= 0:
                    break
                qty = int(remaining / (n_batches - b)) if b < n_batches - 1 else remaining
                qty = max(qty, 0)
                remaining -= qty
                if forced_near_expiry_batch and b == 0:
                    qty = int(qty * 2.2)  # oversized first (earliest-expiry) batch
                    days_to_expiry = int(rng.integers(6, 12))
                elif rng.uniform(0, 1) < near_expiry_bias:
                    days_to_expiry = int(rng.integers(5, 35))  # near-term expiry
                else:
                    days_to_expiry = int(rng.integers(60, shelf_life))
                received_days_ago = int(rng.integers(5, 90))
                rows.append({
                    "batch_id": f"B{batch_seq:05d}", "sku_id": sku_id, "dc_id": dc_id,
                    "qty": qty, "received_date": (TODAY - timedelta(days=received_days_ago)).strftime("%Y-%m-%d"),
                    "expiry_date": (TODAY + timedelta(days=days_to_expiry)).strftime("%Y-%m-%d"),
                })
                batch_seq += 1
    return pd.DataFrame(rows)


def build_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)

    skus_df = pd.DataFrame(SKUS, columns=["sku_id", "name", "category", "criticality", "unit_cost", "margin_per_unit", "shelf_life_days"])
    dcs_df = pd.DataFrame(DCS, columns=["dc_id", "name", "type", "city", "capacity_units"])
    dcs_df["supplier_lead_time_days"] = dcs_df["dc_id"].map(SUPPLIER_LEAD_TIME)

    lead_rows = [{"source_dc": s, "dest_dc": d, "lead_time_days": lt} for (s, d), lt in TRANSFER_LEAD_TIME.items()]
    lead_df = pd.DataFrame(lead_rows)

    promo_df = pd.DataFrame(PROMOTIONS, columns=["sku_id", "dc_id", "start_offset_days", "duration_days", "uplift_pct"])
    promo_df["start_date"] = promo_df["start_offset_days"].apply(lambda o: (START_DATE + timedelta(days=int(o))).strftime("%Y-%m-%d"))
    promo_df["end_date"] = (promo_df["start_offset_days"] + promo_df["duration_days"]).apply(lambda o: (START_DATE + timedelta(days=int(o))).strftime("%Y-%m-%d"))

    demand_df = generate_demand_history()
    batches_df = generate_batches()

    skus_df.to_sql("skus", conn, index=False, if_exists="replace")
    dcs_df.to_sql("dcs", conn, index=False, if_exists="replace")
    lead_df.to_sql("transfer_lead_times", conn, index=False, if_exists="replace")
    promo_df.to_sql("promotions", conn, index=False, if_exists="replace")
    demand_df.to_sql("demand_history", conn, index=False, if_exists="replace")
    batches_df.to_sql("batches", conn, index=False, if_exists="replace")

    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('generated_at', ?)", (datetime.utcnow().isoformat(),))
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('today', ?)", (TODAY.strftime("%Y-%m-%d"),))
    conn.execute("CREATE TABLE IF NOT EXISTS monitoring_runs (run_ts TEXT, sku_id TEXT, dc_id TEXT, action TEXT, risk_score REAL, priority TEXT, stockout_exposure REAL, expiry_exposure REAL)")
    conn.execute("CREATE TABLE IF NOT EXISTS forecast_cache (sku_id TEXT, dc_id TEXT, computed_at TEXT, payload TEXT, PRIMARY KEY(sku_id, dc_id))")
    conn.commit()
    conn.close()
    print(f"Database built at {DB_PATH}")
    print(f"  skus={len(skus_df)} dcs={len(dcs_df)} demand_rows={len(demand_df)} batches={len(batches_df)} promos={len(promo_df)} lead_times={len(lead_df)}")


if __name__ == "__main__":
    build_database()
