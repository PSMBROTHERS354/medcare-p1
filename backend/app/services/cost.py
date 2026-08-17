"""
Cost-of-inaction and priority engine.

Financial assumptions (documented):
  - Stockout cost = shortfall_units * margin_per_unit * P(stockout), where
    P(stockout) is derived from the stockout risk score (0-100 -> 0-1).
  - Expiry cost = expected_expiry_loss_units * unit_cost (full write-off value).
  - cost_weighting parameter (default 1.0) lets the what-if simulator emphasize
    stockout avoidance vs. wastage avoidance (>1 favors stockout avoidance).
"""


def compute_cost_of_inaction(shortfall_units, stockout_risk_score, margin_per_unit,
                              expected_expiry_loss_units, unit_cost, cost_weight_stockout=1.0):
    p_stockout = stockout_risk_score / 100.0
    stockout_cost = round(max(0, shortfall_units) * margin_per_unit * p_stockout * cost_weight_stockout, 2)
    expiry_cost = round(max(0, expected_expiry_loss_units) * unit_cost, 2)
    total = round(stockout_cost + expiry_cost, 2)
    return {
        "stockout_cost_estimate": stockout_cost,
        "expiry_cost_estimate": expiry_cost,
        "total_cost_of_inaction": total,
        "assumptions": {
            "stockout_probability_from_risk_score": round(p_stockout, 3),
            "cost_weight_stockout": cost_weight_stockout,
            "expiry_cost_model": "full unit cost write-off for projected FEFO expiry loss",
            "stockout_cost_model": "shortfall units * margin per unit * stockout probability * weighting",
        },
    }


def compute_priority(combined_risk_score, criticality, total_cost_of_inaction):
    weight = {"Critical": 1.25, "High": 1.1, "Medium": 1.0, "Low": 0.85}.get(criticality, 1.0)
    score = combined_risk_score * weight + min(30, total_cost_of_inaction / 500)
    if score >= 85:
        priority, review_hours, escalation = "Critical", 24, "Immediate escalation to Regional Supply Chain Lead"
    elif score >= 55:
        priority, review_hours, escalation = "High", 48, "Escalate to DC Planning Manager within 48 hours"
    elif score >= 30:
        priority, review_hours, escalation = "Medium", 96, "Flag in weekly planning review"
    else:
        priority, review_hours, escalation = "Low", 168, "No escalation required; routine monitoring"
    return {
        "priority": priority,
        "priority_score": round(score, 1),
        "review_cadence_hours": review_hours,
        "escalation": escalation,
    }
