"""
Network-level search: given a shortage at a destination DC, look across every
other DC for usable excess inventory, and evaluate real transfer feasibility
(expiry, transfer lead time, destination capacity, source's own inventory
position) before ever recommending a supplier replenishment.
"""
from app.db import list_dcs, query_df, get_dc
from app.services import forecasting, inventory, rop as rop_service, cache


def _transfer_lead_time(source_dc, dest_dc):
    df = query_df(
        "SELECT lead_time_days FROM transfer_lead_times WHERE source_dc=? AND dest_dc=?",
        (source_dc, dest_dc),
    )
    if df.empty:
        return None
    return int(df.iloc[0]["lead_time_days"])


def find_network_alternatives(sku_id, dest_dc_id, dest_shortfall_units, dest_criticality, demand_override=None):
    """
    For every other DC, compute its own inventory position and ROP for this SKU,
    determine its *usable excess* (stock above its own ROP + buffer), and assess
    whether transferring to the destination is feasible given expiry, transfer
    lead time, and destination capacity headroom.
    """
    candidates = []
    dest_dc = get_dc(dest_dc_id)
    dest_capacity_headroom = None
    if dest_dc:
        dest_inv = inventory.get_inventory_position(sku_id, dest_dc_id, 1.0)
        dest_capacity_headroom = dest_inv["dc_capacity_headroom"]

    for dc in list_dcs():
        source_dc_id = dc["dc_id"]
        if source_dc_id == dest_dc_id:
            continue
        try:
            fc = forecasting.get_forecast(sku_id, source_dc_id, demand_override) if demand_override else cache.get_cached_forecast(sku_id, source_dc_id)
        except ValueError:
            continue
        inv = inventory.get_inventory_position(sku_id, source_dc_id, fc["sensed_avg_daily"])
        rop_result = rop_service.compute_rop(
            fc["sensed_avg_daily"], fc["demand_std_dev"], dc["supplier_lead_time_days"], dest_criticality,
        )
        usable_excess = max(0, inv["current_stock"] - rop_result["reorder_point"] * 1.1)

        transfer_lt = _transfer_lead_time(source_dc_id, dest_dc_id)

        # expiry check: how much of the excess is safely usable before its own expiry,
        # assuming ~transfer_lt days added transit before it starts being consumed at destination
        exp_batches = inv["batches"]
        expiry_ok_qty = 0
        soonest_expiry_days = None
        for b in exp_batches:
            if soonest_expiry_days is None or b["days_to_expiry"] < soonest_expiry_days:
                soonest_expiry_days = b["days_to_expiry"]
            if transfer_lt is not None and b["days_to_expiry"] > transfer_lt + 14:
                expiry_ok_qty += b["qty"]

        transferable_qty = int(min(usable_excess, expiry_ok_qty))

        capacity_ok = True
        if dest_capacity_headroom is not None:
            capacity_ok = dest_capacity_headroom >= min(transferable_qty, dest_shortfall_units)

        lead_time_ok = transfer_lt is not None and transfer_lt <= 4  # operational feasibility threshold

        feasible = transferable_qty > 0 and lead_time_ok and capacity_ok

        candidates.append({
            "source_dc_id": source_dc_id,
            "source_dc_name": dc["name"],
            "source_current_stock": inv["current_stock"],
            "source_rop": rop_result["reorder_point"],
            "usable_excess_units": int(usable_excess),
            "expiry_safe_transferable_units": transferable_qty,
            "transfer_lead_time_days": transfer_lt,
            "destination_capacity_headroom": dest_capacity_headroom,
            "soonest_batch_expiry_days": soonest_expiry_days,
            "feasible": feasible,
            "reason_if_infeasible": None if feasible else (
                "No usable excess after reserving source's own ROP" if usable_excess <= 0 else
                "Excess batches expire too soon relative to transfer + consumption time" if expiry_ok_qty <= 0 else
                f"Transfer lead time ({transfer_lt} days) exceeds operational threshold" if not lead_time_ok else
                "Destination lacks capacity headroom" if not capacity_ok else "Not feasible"
            ),
        })

    candidates.sort(key=lambda c: (not c["feasible"], -(c["expiry_safe_transferable_units"] or 0)))
    return candidates
