"""
Decision orchestrator.

Pipeline:
  demand sensing -> forecast -> inventory position -> FEFO/expiry -> dynamic ROP
  -> stockout + expiry risk -> root cause -> network search -> transfer feasibility
  -> TRANSFER / REPLENISH / MONITOR -> quantity, timing, priority, explanation

Nothing here is a per-SKU/DC lookup table -- the action emerges from the computed
numbers each time this function runs.
"""
from app.db import get_sku, get_dc
from app.services import forecasting, inventory, rop as rop_service, risk, root_cause, network, cost as cost_service, cache

# below this stockout-risk threshold and above this days-of-supply-vs-lead-time
# ratio, no urgent intervention is required -> MONITOR
STOCKOUT_ACTION_THRESHOLD = 20.0


def evaluate(sku_id, dc_id, demand_override: dict = None, cost_weight_stockout: float = 1.0):
    sku = get_sku(sku_id)
    dc = get_dc(dc_id)
    if not sku or not dc:
        raise ValueError("Unknown SKU or DC")

    if demand_override:
        fc = forecasting.get_forecast(sku_id, dc_id, demand_override)  # live compute: scenario-specific
    else:
        fc = cache.get_cached_forecast(sku_id, dc_id)  # persisted/in-memory cache: fast path
    lead_time_days = dc["supplier_lead_time_days"]
    if demand_override and demand_override.get("lead_time_delta"):
        lead_time_days = max(1, lead_time_days + demand_override["lead_time_delta"])

    inv = inventory.get_inventory_position(sku_id, dc_id, fc["sensed_avg_daily"])
    fefo = inventory.fefo_allocation_and_expiry_risk(sku_id, dc_id, fc["sensed_forecast"])

    rop_result = rop_service.compute_rop(fc["sensed_avg_daily"], fc["demand_std_dev"], lead_time_days, sku["criticality"])

    stockout_score = risk.stockout_risk_score(
        inv["current_stock"], rop_result["reorder_point"], inv["days_of_supply"], lead_time_days, sku["criticality"],
    )
    expiry_score = risk.expiry_risk_score(fefo["expected_expiry_loss_units"], inv["current_stock"])
    combined_risk = round(max(stockout_score, expiry_score) * 0.7 + min(stockout_score, expiry_score) * 0.3, 1)

    shortfall = max(0, rop_result["reorder_point"] - inv["current_stock"])

    # --- network search (only if there's meaningful stockout risk) ---
    network_candidates = []
    network_has_excess = False
    if stockout_score >= STOCKOUT_ACTION_THRESHOLD and shortfall > 0:
        network_candidates = network.find_network_alternatives(
            sku_id, dc_id, shortfall, sku["criticality"], demand_override,
        )
        network_has_excess = any(c["feasible"] for c in network_candidates)

    causes = root_cause.diagnose(
        sku_id, dc_id, sensing_explanation=fc["sensing_explanation"], stockout_risk=stockout_score,
        expiry_risk=expiry_score, lead_time_days=lead_time_days, days_of_supply=inv["days_of_supply"],
        network_has_excess=network_has_excess, current_stock=inv["current_stock"], rop=rop_result["reorder_point"],
    )

    cost_result = cost_service.compute_cost_of_inaction(
        shortfall, stockout_score, sku["margin_per_unit"], fefo["expected_expiry_loss_units"],
        sku["unit_cost"], cost_weight_stockout,
    )
    priority_result = cost_service.compute_priority(combined_risk, sku["criticality"], cost_result["total_cost_of_inaction"])

    # --- the decision itself ---
    if stockout_score < STOCKOUT_ACTION_THRESHOLD and expiry_score < STOCKOUT_ACTION_THRESHOLD:
        action = "MONITOR"
        chosen_source = None
        quantity = 0
        timing_days = None
        explanation = "Stockout and expiry risk are both within normal operating range; no intervention required now."
    else:
        feasible_sources = [c for c in network_candidates if c["feasible"]]
        if feasible_sources:
            action = "TRANSFER"
            chosen_source = feasible_sources[0]
            quantity = int(min(shortfall, chosen_source["expiry_safe_transferable_units"]))
            quantity = max(quantity, 1)
            timing_days = chosen_source["transfer_lead_time_days"]
            explanation = (
                f"{dc['name']} has a shortage (stockout risk {stockout_score}); "
                f"{chosen_source['source_dc_name']} holds usable, expiry-safe excess deliverable within "
                f"{timing_days} day(s) and within destination capacity, so a transfer is recommended over supplier replenishment."
            )
        elif shortfall > 0 or stockout_score >= STOCKOUT_ACTION_THRESHOLD:
            action = "REPLENISH"
            chosen_source = None
            quantity = int(max(shortfall, 1))
            timing_days = lead_time_days
            infeasible_reasons = [c["reason_if_infeasible"] for c in network_candidates if not c["feasible"]]
            reason_text = "; ".join(sorted(set(infeasible_reasons))) if infeasible_reasons else "no sister DC currently holds usable excess"
            explanation = (
                f"{dc['name']} has a shortage (stockout risk {stockout_score}) and no feasible network transfer exists "
                f"({reason_text}); recommending supplier replenishment with a {lead_time_days}-day lead time."
            )
        else:
            action = "MONITOR"
            chosen_source = None
            quantity = 0
            timing_days = None
            explanation = f"Expiry risk elevated ({expiry_score}) but stockout risk is manageable; monitor FEFO consumption."

    replenishment_frequency = rop_service.compute_replenishment_frequency(
        quantity, fc["sensed_avg_daily"], inv["current_stock"], rop_result["reorder_point"],
    )

    return {
        "sku": sku, "dc": dc,
        "forecast": fc,
        "inventory": {k: v for k, v in inv.items() if k != "batches"},
        "batches": inv["batches"],
        "fefo": fefo,
        "rop": rop_result,
        "risk": {
            "stockout_risk_score": stockout_score, "stockout_risk_level": risk.classify_risk(stockout_score),
            "expiry_risk_score": expiry_score, "expiry_risk_level": risk.classify_risk(expiry_score),
            "combined_risk_score": combined_risk,
        },
        "root_causes": causes,
        "network_alternatives": network_candidates,
        "cost": cost_result,
        "priority": priority_result,
        "decision": {
            "action": action,
            "quantity": quantity,
            "source_dc": chosen_source["source_dc_id"] if chosen_source else None,
            "source_dc_name": chosen_source["source_dc_name"] if chosen_source else None,
            "destination_dc": dc_id,
            "timing_days": timing_days,
            "shortfall_units": int(shortfall),
            "explanation": explanation,
            "replenishment_cycle_days": replenishment_frequency["replenishment_cycle_days"],
            "estimated_replenishments_per_year": replenishment_frequency["estimated_replenishments_per_year"],
        },
    }
