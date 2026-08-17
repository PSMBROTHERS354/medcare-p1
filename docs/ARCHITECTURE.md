# Architecture

## Component diagram

```
                         ┌────────────────────────────┐
                         │   Frontend (React + Vite)   │
                         │  4 screens, no business     │
                         │  logic — consumes API only  │
                         └──────────────┬───────────────┘
                                        │ REST (JSON over fetch)
                         ┌──────────────▼───────────────┐
                         │        FastAPI (main.py)      │
                         │  validation, routing, CORS    │
                         └──────────────┬───────────────┘
                                        │
        ┌───────────────────────────────┼────────────────────────────────┐
        │                               │                                │
┌───────▼────────┐   ┌──────────────────▼─────────────┐   ┌──────────────▼───────┐
│ forecasting.py  │   │        decision.py             │   │      cache.py        │
│ Holt-Winters    │──►│  orchestrates the full pipeline │◄──│ persisted forecast   │
│ + sensing       │   │  demand→forecast→inventory→     │   │ cache (SQLite +      │
│ multiplier      │   │  expiry→ROP→risk→root cause→    │   │ in-memory), warmed   │
└─────────────────┘   │  network search→decision        │   │ at process startup   │
                       └──────┬──────┬──────┬──────┬────┘   └───────────────────────┘
                              │      │      │      │
                  ┌───────────▼┐ ┌──▼───┐ ┌▼─────┐ ┌▼─────────┐
                  │inventory.py│ │rop.py│ │risk.py│ │network.py│
                  │FEFO+expiry │ │      │ │       │ │transfer  │
                  └────────────┘ └──────┘ └───────┘ │feasibility│
                                                     └───────────┘
                              │
                  ┌───────────▼─────────┐    ┌──────────────┐
                  │   root_cause.py     │    │   cost.py    │
                  │  ranked cause list  │    │ cost+priority│
                  └──────────────────────┘    └──────────────┘
                              │
                  ┌───────────▼──────────────┐
                  │  SQLite (medcare.db)      │
                  │  skus, dcs, demand_history,│
                  │  batches, promotions,      │
                  │  transfer_lead_times,      │
                  │  forecast_cache,           │
                  │  monitoring_runs           │
                  └────────────────────────────┘
```

## Design principles followed

- **The frontend has zero business logic.** Every number shown in the UI
  (forecast, ROP, risk score, recommended action, priority) is computed
  server-side and returned as-is. The frontend only formats and displays.
- **The decision orchestrator (`decision.py`) is the single place the final
  action is decided.** No other module and no UI component makes that call.
- **Nothing is a lookup table keyed by SKU/DC.** Every quantity is derived from
  the current state of the demand-sensing, forecasting, inventory, and network
  modules at the time of the request (or from the warmed cache, for forecasts
  specifically — see Performance below).
- **The network search always runs before REPLENISH is considered**, per the
  master requirement that supplier replenishment must never be the first
  answer to a shortage.

## Performance approach

Holt-Winters (statsmodels `ExponentialSmoothing`) is not free to fit — running
it for all 30 SKU × DC combinations on every request made bulk endpoints
(`/api/network-health`, `/api/network-map`, `/api/attention-queue`) take **~14
seconds** in early testing. This violated the "UI must feel responsive"
requirement, so a forecast cache (`services/cache.py`) was added:

- On FastAPI startup, forecasts for all 30 combinations are computed once and
  stored both in-process (a Python dict) and persisted to a `forecast_cache`
  SQLite table.
- Any request that does **not** need a live what-if override reads from this
  cache.
- What-if requests (`POST /api/what-if`) always compute live, because they need
  fresh numbers for the exact scenario the user is exploring — but that's a
  single SKU/DC fit (plus a handful of network-search fits for sister DCs), not
  all 30.

Measured effect (see `docs/PERFORMANCE.md` for the full benchmark): bulk
endpoints dropped from ~14,000ms to ~400ms; single-SKU recommendation lookups
run in ~30-40ms from cache.

## Data flow for one recommendation

1. `GET /api/recommendation/{sku}/{dc}` hits `main.py`, which validates the
   SKU/DC and calls `decision.evaluate(sku, dc)`.
2. `decision.evaluate` pulls the cached forecast (`cache.get_cached_forecast`),
   computes inventory position and FEFO/expiry risk (`inventory.py`), computes
   the dynamic ROP (`rop.py`), and computes stockout/expiry risk scores
   (`risk.py`).
3. If stockout risk is above the action threshold, `network.py` is invoked to
   search every sister DC for usable, expiry-safe, capacity-feasible excess.
4. `root_cause.py` produces a ranked list of contributing factors using the
   same numbers computed in steps 2-3.
5. `cost.py` computes the cost of inaction and the resulting priority /
   review cadence / escalation.
6. `decision.evaluate` applies the TRANSFER → REPLENISH → MONITOR decision
   rule and returns the full payload.

No step in this chain reads a hardcoded outcome for the specific SKU/DC pair.
