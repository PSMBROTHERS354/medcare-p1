# Forecast Methodology

## Model

Baseline forecast uses `statsmodels.tsa.holtwinters.ExponentialSmoothing` with
additive trend and additive weekly seasonality (`seasonal_periods=7`),
fit with `initialization_method="estimated"`. If the fit fails for any reason
(e.g. degenerate series), the code falls back to a 28-day moving average
rather than crashing.

## Holdout evaluation (real, not hardcoded)

For every SKU × DC combination, the last **14 days** of the 180-day history
are held out. The model is fit only on the remaining ~166 days, then used to
forecast those 14 held-out days. The forecast is compared against the actual
recorded demand for those days to compute:

- **MAE** — mean absolute error
- **RMSE** — root mean squared error
- **MAPE** — mean absolute percentage error (computed only over days with
  non-zero actual demand, to avoid division by zero; reported as `null` if no
  such days exist in the holdout window)

These numbers are recomputed on every forecast request (or read from the
warmed cache) — never hardcoded. `test_18_forecast_metrics_are_computed_not_hardcoded`
explicitly checks that two different SKU/DC combinations do not return
identical metrics.

## Demand sensing layer

Demand sensing is a **multiplier applied on top of the Holt-Winters forecast**,
not a separate model. It is derived from three components, each computed from
recent (last-14-day) data:

1. **Flu component** — the mean of the `flu_signal` column over the most
   recent 3 days. This is 0 when no flu signal is active, and ramps toward the
   engineered +60% as the flu window progresses (see `data_gen.py`).
2. **Promotion component** — a flat +10% if any promotion was active in the
   last 7 days.
3. **Distributor order momentum component** — compares the average size of
   recent distributor orders to the average recent daily demand; if
   distributors are ordering meaningfully more (or less) than current demand
   would suggest, this nudges the sensed forecast up (or down), capped at
   ±15%.

The three components sum into a single multiplier applied to the Holt-Winters
baseline to produce the **sensed forecast**. This is why, for example,
`test_02_flu_signal_increases_sensed_demand` can assert that toggling the flu
override produces a measurably higher sensed forecast — the multiplier is a
real, inspectable number (`sensing_explanation` in the API payload), not a
cosmetic label.

## Baseline vs. sensed comparison

Both the baseline (Holt-Winters only) and sensed (Holt-Winters × sensing
multiplier) forecasts are evaluated against the same holdout window, and the
comparison is reported honestly:

- If the sensed forecast's holdout MAPE is lower, the API returns a note that
  sensing improved accuracy for that window.
- If it's higher, the API says so explicitly — sensing does not always help
  (e.g. if the holdout window predates an active flu signal, the sensing
  multiplier legitimately doesn't have anything relevant to correct for).
- If there isn't enough non-zero holdout data for a meaningful MAPE, the API
  says that too, rather than fabricating a comparison.

## What-if overrides

The Decision Studio's what-if simulator passes a `demand_override` dict
(`flu_active`, `demand_change_pct`, `lead_time_delta`) into
`sensing_multiplier()`, which overrides the corresponding component(s) before
recomputing the forward forecast. This recalculates the *forward* 14-day
forecast live; it does not retroactively change the holdout evaluation (which
always reflects the model's real historical accuracy, independent of any
hypothetical scenario being explored).
