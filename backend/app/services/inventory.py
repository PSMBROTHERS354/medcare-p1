"""
Inventory position, batch/expiry tracking, and real FEFO (First-Expiry-First-Out)
allocation logic.

FEFO here is not a label: batches are sorted earliest-expiry-first and consumed
against a genuine forward demand projection (the sensed daily forecast), so the
expiry-risk calculation compares future expiry dates against future projected
consumption -- not against historical demand (the bug the spec explicitly warns
against).
"""
import pandas as pd
from datetime import datetime
from app.db import query_df, get_today, get_dc


def get_batches(sku_id, dc_id):
    df = query_df(
        "SELECT batch_id, qty, received_date, expiry_date FROM batches WHERE sku_id=? AND dc_id=? AND qty > 0 ORDER BY expiry_date ASC",
        (sku_id, dc_id),
    )
    return df


def get_inventory_position(sku_id, dc_id, sensed_avg_daily_demand: float):
    today = pd.Timestamp(get_today())
    batches = get_batches(sku_id, dc_id)
    current_stock = int(batches["qty"].sum()) if len(batches) else 0

    dc = get_dc(dc_id)
    capacity = dc["capacity_units"] if dc else None

    days_of_supply = round(current_stock / sensed_avg_daily_demand, 1) if sensed_avg_daily_demand > 0 else None

    batch_list = []
    for _, b in batches.iterrows():
        exp = pd.Timestamp(b["expiry_date"])
        days_to_expiry = (exp - today).days
        batch_list.append({
            "batch_id": b["batch_id"], "qty": int(b["qty"]),
            "received_date": b["received_date"], "expiry_date": b["expiry_date"],
            "days_to_expiry": int(days_to_expiry),
        })

    return {
        "current_stock": current_stock,
        "batches": batch_list,
        "days_of_supply": days_of_supply,
        "dc_capacity_units": capacity,
        "dc_capacity_headroom": (capacity - current_stock) if capacity is not None else None,
    }


def fefo_allocation_and_expiry_risk(sku_id, dc_id, sensed_daily_forecast: list):
    """
    Walk batches earliest-expiry-first, consuming against the *forward* sensed
    daily forecast (list of projected daily demand for the forecast horizon,
    extended with the last known daily rate beyond the explicit horizon).

    Any batch whose expiry date arrives before FEFO consumption would exhaust it
    is flagged as at-risk-of-expiry, with the expected wastage quantity.
    """
    today = pd.Timestamp(get_today())
    batches = get_batches(sku_id, dc_id)
    if batches.empty:
        return {"fefo_allocation": [], "expected_expiry_loss_units": 0, "at_risk_batches": [], "usable_qty_before_first_risk_expiry": 0}

    horizon = len(sensed_daily_forecast) if sensed_daily_forecast else 14
    last_rate = sensed_daily_forecast[-1] if sensed_daily_forecast else 1.0
    # extend projection out to 180 days using last known sensed rate, so long-dated
    # batches can still be evaluated against a demand projection instead of falling
    # back to raw historical averages.
    daily_projection = list(sensed_daily_forecast) + [last_rate] * max(0, 180 - horizon)

    cursor_day = 0  # index into daily_projection representing "today + cursor_day"
    remaining_today_capacity = daily_projection[0] if daily_projection else last_rate

    allocation = []
    at_risk_batches = []
    expected_loss = 0

    for _, b in batches.iterrows():
        qty_remaining_in_batch = int(b["qty"])
        expiry = pd.Timestamp(b["expiry_date"])
        days_to_expiry = (expiry - today).days
        consumed_before_expiry = 0
        day_ptr = cursor_day
        cap_ptr = remaining_today_capacity

        while qty_remaining_in_batch > 0 and day_ptr < days_to_expiry and day_ptr < len(daily_projection):
            take = min(qty_remaining_in_batch, cap_ptr)
            qty_remaining_in_batch -= take
            consumed_before_expiry += take
            cap_ptr -= take
            if cap_ptr <= 0.0001:
                day_ptr += 1
                cap_ptr = daily_projection[day_ptr] if day_ptr < len(daily_projection) else last_rate

        cursor_day = day_ptr
        remaining_today_capacity = cap_ptr

        at_risk_qty = int(round(qty_remaining_in_batch))
        allocation.append({
            "batch_id": b["batch_id"], "qty": int(b["qty"]),
            "expiry_date": b["expiry_date"], "days_to_expiry": int(days_to_expiry),
            "projected_consumed_before_expiry": int(round(consumed_before_expiry)),
            "projected_expiry_loss": at_risk_qty,
        })
        if at_risk_qty > 0:
            at_risk_batches.append({
                "batch_id": b["batch_id"], "at_risk_qty": at_risk_qty,
                "expiry_date": b["expiry_date"], "days_to_expiry": int(days_to_expiry),
            })
            expected_loss += at_risk_qty

    return {
        "fefo_allocation": allocation,
        "expected_expiry_loss_units": int(expected_loss),
        "at_risk_batches": at_risk_batches,
    }
