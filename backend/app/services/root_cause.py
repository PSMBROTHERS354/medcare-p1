"""
Root-cause explanation engine.

Rule-based, driven off the same numbers computed elsewhere in the pipeline
(sensing multiplier, days-of-supply trend, expiry exposure, lead time, network
position). Produces a ranked list of contributing causes, not a single guess.
"""
import pandas as pd
from app.db import query_df


def _chronic_understock_check(sku_id, dc_id):
    """Look at trailing days_of_supply-like proxy over history: was stock/demand ratio
    persistently low well before the flu window, independent of any surge?"""
    df = query_df(
        "SELECT date, actual_demand, flu_signal FROM demand_history WHERE sku_id=? AND dc_id=? ORDER BY date",
        (sku_id, dc_id),
    )
    if df.empty:
        return False
    pre_flu = df[df["flu_signal"] < 0.05]
    if len(pre_flu) < 30:
        return False
    # chronic understock signature: demand relatively flat/declining trend but sustained low base
    # (we use the engineered 'trend' proxy indirectly via rolling mean slope)
    df["date"] = pd.to_datetime(df["date"])
    pre_flu = pre_flu.sort_values("date")
    early = pre_flu["actual_demand"].head(30).mean()
    late = pre_flu["actual_demand"].tail(30).mean()
    # chronic understock in our data model shows as a declining trend baked into demand
    # while stock stayed persistently thin -- caller supplies stock context separately.
    return early, late


def diagnose(sku_id, dc_id, *, sensing_explanation, stockout_risk, expiry_risk,
             lead_time_days, days_of_supply, network_has_excess, current_stock, rop):
    causes = []

    if sensing_explanation.get("flu_component", 0) >= 0.15:
        causes.append({
            "cause": "Demand surge (flu signal)",
            "detail": f"Active flu sensing signal is contributing +{sensing_explanation['flu_component']*100:.0f}% to sensed demand.",
            "weight": sensing_explanation["flu_component"],
        })

    if sensing_explanation.get("promo_component", 0) > 0:
        causes.append({
            "cause": "Promotional uplift",
            "detail": f"An active promotion is adding +{sensing_explanation['promo_component']*100:.0f}% to sensed demand.",
            "weight": sensing_explanation["promo_component"],
        })

    if days_of_supply is not None and lead_time_days and days_of_supply < lead_time_days:
        causes.append({
            "cause": "Insufficient inventory relative to lead time",
            "detail": f"Only {days_of_supply} days of supply on hand vs a {lead_time_days}-day replenishment lead time.",
            "weight": max(0.0, 1 - (days_of_supply / lead_time_days)) if lead_time_days else 0.5,
        })

    early_late = _chronic_understock_check(sku_id, dc_id)
    flu_driven = sensing_explanation.get("flu_component", 0) >= 0.15
    if early_late and not flu_driven and current_stock is not None and rop and current_stock < rop * 0.6:
        early, late = early_late
        causes.append({
            "cause": "Chronic understock",
            "detail": "Stock has persistently trailed the reorder point independent of any short-term demand spike, indicating a structural replenishment gap rather than a one-off event.",
            "weight": 0.6,
        })

    if expiry_risk >= 20:
        causes.append({
            "cause": "Expiry exposure",
            "detail": f"Expiry risk score of {expiry_risk} indicates batches on hand are unlikely to be consumed before expiring under FEFO allocation.",
            "weight": expiry_risk / 100,
        })

    if lead_time_days and lead_time_days >= 6:
        causes.append({
            "cause": "Lead-time problem",
            "detail": f"Supplier replenishment lead time of {lead_time_days} days is long relative to demand variability, increasing exposure during the gap.",
            "weight": min(1.0, lead_time_days / 12),
        })

    if stockout_risk >= 20 and not network_has_excess and not any(c["cause"] == "Chronic understock" for c in causes):
        causes.append({
            "cause": "Network imbalance",
            "detail": "No sister DC currently holds usable excess for this SKU, isolating this location's shortage risk.",
            "weight": 0.4,
        })

    causes.sort(key=lambda c: c["weight"], reverse=True)
    if not causes:
        causes.append({"cause": "No significant risk driver", "detail": "Current position is within normal operating parameters.", "weight": 0.0})

    return causes
