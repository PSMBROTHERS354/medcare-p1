"""
Dynamic Reorder Point (ROP) calculation.

ROP = demand during lead time + safety stock

Safety stock uses a z-score derived from SKU criticality (higher criticality ->
higher target service level -> higher z -> more safety stock), demand variability
(std dev of recent daily demand), and lead time. This means ROP genuinely moves
when the sensed forecast, lead time, or variability change -- nothing here is a
fixed constant per SKU.
"""
import math

CRITICALITY_Z = {
    "Critical": 2.05,   # ~98% service level
    "High": 1.65,       # ~95%
    "Medium": 1.28,     # ~90%
    "Low": 0.84,         # ~80%
}


def compute_rop(sensed_avg_daily_demand: float, demand_std_dev: float, lead_time_days: float, criticality: str):
    z = CRITICALITY_Z.get(criticality, 1.28)
    demand_during_lead_time = sensed_avg_daily_demand * lead_time_days
    # safety stock formula: z * sigma_demand * sqrt(lead_time)  (lead time assumed fixed/known here;
    # if lead-time variability data were available it would be incorporated too)
    safety_stock = z * max(demand_std_dev, 0.0) * math.sqrt(max(lead_time_days, 0.01))
    rop = demand_during_lead_time + safety_stock
    return {
        "z_score": z,
        "demand_during_lead_time": round(demand_during_lead_time, 1),
        "safety_stock": round(safety_stock, 1),
        "reorder_point": round(rop, 1),
        "lead_time_days": lead_time_days,
    }


def compute_replenishment_frequency(quantity: float, sensed_avg_daily_demand: float, current_stock: float, reorder_point: float):
    """
    Estimate replenishment frequency under the continuous-review (reorder-point)
    policy already used elsewhere in this engine: how many days the recommended
    order (for TRANSFER/REPLENISH) -- or the stock currently held above the
    reorder point (for MONITOR) -- is expected to last at the sensed demand
    rate, and the implied number of replenishment cycles per year.

    This is additive reporting derived from numbers already computed by
    compute_rop() and the decision orchestrator. It does NOT change the
    reorder point, the recommended quantity, or the TRANSFER/REPLENISH/MONITOR
    decision itself -- it answers "how often would replenishment recur at this
    rate", which a continuous-review (s, ROP) system expresses as a cycle
    length rather than a fixed periodic schedule.
    """
    if sensed_avg_daily_demand is None or sensed_avg_daily_demand <= 0:
        return {"replenishment_cycle_days": None, "estimated_replenishments_per_year": None}

    if quantity and quantity > 0:
        cycle_days = quantity / sensed_avg_daily_demand
    else:
        buffer_above_rop = max(0.0, (current_stock or 0) - (reorder_point or 0))
        cycle_days = buffer_above_rop / sensed_avg_daily_demand

    cycle_days = round(cycle_days, 1)
    per_year = round(365 / cycle_days, 1) if cycle_days > 0 else None
    return {"replenishment_cycle_days": cycle_days, "estimated_replenishments_per_year": per_year}
