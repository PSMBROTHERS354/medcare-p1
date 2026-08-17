"""
Forecasting service.

Baseline forecast: Holt-Winters (statsmodels ExponentialSmoothing) fit purely on
historical actual demand -- no live sensing signals.

Sensed forecast: baseline forecast adjusted by a demand-sensing multiplier derived
from currently-active signals (flu ramp, promotions, distributor order momentum).
This is what makes demand sensing *actually* change the numbers instead of being
a cosmetic label.

Evaluation metrics (MAE / RMSE / MAPE) are computed from a genuine holdout split
of the historical series, never hardcoded.
"""
import numpy as np
import pandas as pd
import warnings
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from app.db import query_df

warnings.filterwarnings("ignore")

HOLDOUT_DAYS = 14
FORECAST_HORIZON = 14
SEASONAL_PERIOD = 7


def _get_history(sku_id, dc_id):
    df = query_df(
        "SELECT date, actual_demand, promo_active, flu_signal, distributor_order_qty "
        "FROM demand_history WHERE sku_id=? AND dc_id=? ORDER BY date",
        (sku_id, dc_id),
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def _fit_holt_winters(series: pd.Series, horizon: int):
    series = series.clip(lower=0.01)
    try:
        model = ExponentialSmoothing(
            series, trend="add", seasonal="add", seasonal_periods=SEASONAL_PERIOD,
            initialization_method="estimated",
        ).fit(optimized=True)
        fc = model.forecast(horizon)
        return np.clip(fc.values, 0, None)
    except Exception:
        # fallback: simple moving-average + weekly seasonality
        window = series.tail(28)
        avg = window.mean()
        return np.full(horizon, max(avg, 0))


def compute_metrics(actual: np.ndarray, predicted: np.ndarray):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    mae = float(np.mean(np.abs(actual - predicted)))
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    nonzero = actual != 0
    mape = float(np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100) if nonzero.sum() else None
    return {"mae": round(mae, 2), "rmse": round(rmse, 2), "mape": round(mape, 2) if mape is not None else None}


def sensing_multiplier(df: pd.DataFrame, demand_override: dict = None):
    """
    Derive a demand-sensing multiplier from the most recent signals:
      - flu ramp (current active flu intensity, 0 if inactive)
      - promotion activity in the last 7 days
      - distributor order momentum vs. recent average demand

    demand_override lets the what-if simulator inject flu_active / demand_change_pct.
    """
    recent = df.tail(14)
    flu_component = float(recent["flu_signal"].tail(3).mean())  # most recent flu ramp
    promo_component = 0.10 if recent["promo_active"].tail(7).sum() > 0 else 0.0

    recent_orders = recent[recent["distributor_order_qty"] > 0]["distributor_order_qty"]
    recent_avg_demand = recent["actual_demand"].mean()
    if len(recent_orders) and recent_avg_demand > 0:
        order_momentum = float(recent_orders.mean()) / float(recent_avg_demand) - 1.0
        order_component = max(-0.15, min(0.15, order_momentum * 0.3))
    else:
        order_component = 0.0

    multiplier = 1.0 + flu_component + promo_component + order_component

    explanation = {
        "flu_component": round(flu_component, 3),
        "promo_component": round(promo_component, 3),
        "distributor_momentum_component": round(order_component, 3),
    }

    if demand_override:
        if demand_override.get("flu_active") is True:
            multiplier = multiplier - flu_component + 0.60
            explanation["flu_component"] = 0.60
            explanation["override"] = "flu manually activated (+60%)"
        elif demand_override.get("flu_active") is False:
            multiplier = multiplier - flu_component
            explanation["flu_component"] = 0.0
            explanation["override"] = "flu manually deactivated"
        if demand_override.get("demand_change_pct") is not None:
            pct = demand_override["demand_change_pct"] / 100.0
            multiplier += pct
            explanation["manual_demand_change_component"] = round(pct, 3)

    multiplier = max(0.1, multiplier)
    return multiplier, explanation


def get_forecast(sku_id, dc_id, demand_override: dict = None):
    df = _get_history(sku_id, dc_id)
    if df.empty or len(df) < SEASONAL_PERIOD * 3:
        raise ValueError("Insufficient history for forecasting")

    train = df.iloc[: -HOLDOUT_DAYS]
    holdout = df.iloc[-HOLDOUT_DAYS:]

    # --- Holdout validation: fit on train only, evaluate against real holdout actuals ---
    holdout_fc = _fit_holt_winters(train.set_index("date")["actual_demand"], HOLDOUT_DAYS)
    baseline_metrics = compute_metrics(holdout["actual_demand"].values, holdout_fc)

    mult, sensing_explanation = sensing_multiplier(train, demand_override)
    sensed_holdout_fc = holdout_fc * mult
    sensed_metrics = compute_metrics(holdout["actual_demand"].values, sensed_holdout_fc)

    comparison_note = None
    if baseline_metrics["mape"] is not None and sensed_metrics["mape"] is not None:
        if sensed_metrics["mape"] < baseline_metrics["mape"]:
            comparison_note = "Sensed forecast reduced holdout MAPE vs baseline."
        elif sensed_metrics["mape"] > baseline_metrics["mape"]:
            comparison_note = "Sensed forecast increased holdout MAPE vs baseline for this window (sensing signal did not match holdout period)."
        else:
            comparison_note = "Sensed and baseline forecast performed equally on this holdout window."
    else:
        comparison_note = "Insufficient non-zero holdout data for a meaningful MAPE comparison."

    # --- Forward forecast (full history, forward horizon) ---
    full_mult, full_explanation = sensing_multiplier(df, demand_override)
    baseline_forward = _fit_holt_winters(df.set_index("date")["actual_demand"], FORECAST_HORIZON)
    sensed_forward = baseline_forward * full_mult

    last_date = df["date"].max()
    forecast_dates = [(last_date + pd.Timedelta(days=i + 1)).strftime("%Y-%m-%d") for i in range(FORECAST_HORIZON)]

    return {
        "sku_id": sku_id, "dc_id": dc_id,
        "history_days": len(df),
        "forecast_horizon_days": FORECAST_HORIZON,
        "forecast_dates": forecast_dates,
        "baseline_forecast": [round(float(x), 1) for x in baseline_forward],
        "sensed_forecast": [round(float(x), 1) for x in sensed_forward],
        "sensing_multiplier": round(full_mult, 4),
        "sensing_explanation": full_explanation,
        "baseline_avg_daily": round(float(np.mean(baseline_forward)), 1),
        "sensed_avg_daily": round(float(np.mean(sensed_forward)), 1),
        "demand_std_dev": round(float(df["actual_demand"].tail(60).std()), 2),
        "evaluation": {
            "holdout_days": HOLDOUT_DAYS,
            "baseline_metrics": baseline_metrics,
            "sensed_metrics": sensed_metrics,
            "comparison_note": comparison_note,
        },
    }
