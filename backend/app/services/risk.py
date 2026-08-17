"""
Stockout + expiry risk engine.

Risk is computed dynamically from current inventory position, ROP, forecast, and
expiry exposure -- not from static per-SKU labels. Changing demand, lead time,
inventory, or criticality genuinely moves the score.
"""

CRITICALITY_WEIGHT = {"Critical": 1.3, "High": 1.15, "Medium": 1.0, "Low": 0.85}


def stockout_risk_score(current_stock, rop, days_of_supply, lead_time_days, criticality):
    """
    0-100 score. Rises as stock falls below ROP and as days_of_supply approaches
    (or falls below) the lead time needed to replenish.
    """
    weight = CRITICALITY_WEIGHT.get(criticality, 1.0)
    if rop <= 0:
        rop_component = 0
    else:
        # how far below ROP, as a fraction of ROP (can exceed 1 if deeply negative coverage)
        shortfall_frac = max(0.0, (rop - current_stock) / rop)
        rop_component = min(1.0, shortfall_frac) * 70

    if days_of_supply is None:
        dos_component = 0
    else:
        # risk rises sharply once days_of_supply < lead_time_days (can't replenish in time)
        if lead_time_days <= 0:
            dos_component = 0
        else:
            ratio = days_of_supply / lead_time_days
            dos_component = max(0.0, min(1.0, 1.5 - ratio)) * 30

    score = min(100, (rop_component + dos_component) * weight)
    return round(score, 1)


def expiry_risk_score(expected_expiry_loss_units, current_stock):
    if current_stock <= 0:
        return 0.0
    loss_frac = expected_expiry_loss_units / current_stock
    score = min(100, loss_frac * 100)
    return round(score, 1)


def classify_risk(score):
    if score >= 70:
        return "Critical"
    if score >= 45:
        return "High"
    if score >= 20:
        return "Medium"
    return "Low"
