# P1 — Requirement Traceability Matrix

Source documents: official Cognizant P1 use-case table (MedCare Pharma — Demand
Sensing & Replenishment Planning), evaluation-criteria slides ("Factors to Consider",
"Evaluation Criteria — Guideline", "Expectation of Best Solution"), and the master
build prompt derived from them.

Status legend: ✅ Covered · 🟡 Partially covered · ❌ Missing

| ID | Requirement (source) | Data required | Backend module | API endpoint | UI location | Test | Status |
|----|----|----|----|----|----|----|----|
| P1-R01 | Sense near-term demand shifts using signals (promotions, seasonality, leading indicators / flu) | demand_history, promotions | `services/forecasting.py: sensing_multiplier` | `GET /api/forecast/{sku}/{dc}` | Screen 2 forecast chart + sensing explanation | test_02, test_03, test_18 | ✅ |
| P1-R02 | Improve short-term forecast accuracy using sensing signals, measured with real metrics | demand_history (holdout split) | `services/forecasting.py` (Holt-Winters, MAE/RMSE/MAPE) | `GET /api/forecast/{sku}/{dc}` | Screen 2 subtitle ("holdout MAPE") | test_18 | ✅ |
| P1-R03 | Design expiry-aware allocation logic (FEFO) to reduce write-offs | batches (expiry, qty) | `services/inventory.py: fefo_allocation_and_expiry_risk` | `GET /api/inventory/{sku}/{dc}`, embedded in `GET /api/recommendation/...` | Screen 2 "Batch / Expiry Detail" table | test_08, test_09 | ✅ |
| P1-R04 | Optimize replenishment quantity and frequency across DCs (dynamic ROP) | forecast, lead time, criticality | `services/rop.py: compute_rop, compute_replenishment_frequency` | `GET /api/recommendation/{sku}/{dc}` | Screen 2 ROP stat card + "FREQUENCY" field in Recommendation Explanation | test_04, test_14, test_15, test_24 | ✅ |
| P1-R05 | Reduce stockouts of critical SKUs during demand surges | risk engine + network search + decision orchestrator | `services/risk.py`, `services/network.py`, `services/decision.py` | `GET /api/recommendation/{sku}/{dc}` | Screen 2 risk cards, Screen 1 queue | test_01, test_05, test_06, test_11 | ✅ |
| P1-R06 | Recommend a review cadence / escalation process for shortage situations | risk score, criticality, cost of inaction | `services/cost.py: compute_priority` | embedded in recommendation payload | Screen 2 "Recommendation Explanation" (REVIEW / ESCALATION) | test_11, test_19 | ✅ |
| P1-R07 | Balance safety stock vs. wastage across DCs (network-level decisioning) | inventory position of every DC, transfer lead times, capacity | `services/network.py`, `services/decision.py` | `GET /api/network/{sku}/{dc}`, `GET /api/network-map` | Screen 1 risk map, Screen 2 network alternatives | test_05, test_06, test_17 | ✅ |
| P1-R08 | Warehouse capacity & lead times must be operationally meaningful (not unused fields) | dcs.capacity_units, transfer_lead_times | `services/network.py` (capacity_ok / lead_time_ok gating) | `GET /api/network/{sku}/{dc}` | Screen 2 network alternatives (capacity headroom shown) | test_17 | ✅ |
| P1-R09 | Distributor order pattern signal feeds demand sensing | demand_history.distributor_order_qty | `services/forecasting.py: sensing_multiplier` (order_component) | `GET /api/forecast/{sku}/{dc}` | Screen 2 sensing explanation line | test_02 (indirect), test_23 (dedicated, isolated) | ✅ |
| P1-R10 | What-if simulation on demand, flu, lead time, cost weighting | live override to forecasting/decision engine | `services/forecasting.py`, `services/decision.py` (demand_override) | `POST /api/what-if` | Screen 3 (Decision Studio) | test_13, test_14, test_15, test_22 | ✅ |
| P1-R11 | Network health / monitoring view | aggregate of all recommendation runs | `main.py: get_network_health, monitoring_metrics, monitoring_history` | `GET /api/network-health`, `/api/monitoring/*` | Screen 4 (Monitoring) | test_16 | ✅ |
| P1-R12 | No hardcoded forecasts / risk scores / recommendations / metrics | — | all `services/*` modules compute from live data each call | all endpoints | — | test_18 (metrics differ across combos) | ✅ |
| P1-R13 | Input validation; invalid input must not crash the server | — | `main.py: _validate_sku_dc`, Pydantic `WhatIfRequest` | all endpoints | — | test_20, test_20b | ✅ |
| P1-R14 | Four screens only: Command Center, SKU/DC Intelligence, Decision Studio, Monitoring | — | — | — | `frontend/src/pages/*` (exactly 4 route pages) | manual screen walkthrough | ✅ |
| P1-R15 | Enterprise pharma visual identity (dark teal/navy sidebar, restrained accents, no AI-dashboard tropes) | — | — | — | `Shell.css`, `index.css` design tokens | manual visual review | ✅ |
| P1-R16 | Performance: don't re-fit models on every network-wide request | — | `services/cache.py` (persisted + in-memory forecast cache, warmed at startup) | — | — | benchmark (see PERFORMANCE.md) | ✅ |
| P1-R17 | Cost of inaction / financial impact, with documented assumptions | margin_per_unit, unit_cost | `services/cost.py` | embedded in recommendation payload | Screen 1 stat card, Screen 3 diff row | test_12 | ✅ |
| P1-R18 | Root-cause explanation for at-risk SKUs | sensing, inventory, expiry, network state | `services/root_cause.py` | embedded in recommendation payload | Screen 2 "Root Cause" panel | test_10 (indirect) | ✅ |
| P1-R19 | Priority levels (Critical/High/Medium/Low) | risk + cost + criticality | `services/cost.py: compute_priority` | embedded in recommendation payload | Screen 1/2/4 badges | test_11 | ✅ |
| P1-R20 | Synthetic data must demonstrate the P1 problem, not be random | — | `app/data_gen.py` (engineered scenario anchors) | `GET /api/scenarios` | — | manual verification (flu shortage, chronic understock, transfer-infeasible, healthy, near-expiry all confirmed to produce the expected action in `docs/test_report_run1.txt` and ad-hoc checks) | ✅ |
| P1-R21 | Replenishment *frequency* planning, not just quantity (continuous-review reorder cycle) | quantity, sensed avg daily demand, current stock, ROP | `services/rop.py: compute_replenishment_frequency` | embedded in `GET /api/recommendation/{sku}/{dc}` (`decision.replenishment_cycle_days`, `decision.estimated_replenishments_per_year`) | Screen 2 "FREQUENCY" field in Recommendation Explanation | test_24 | ✅ |

## Coverage summary

- **Covered:** 21 / 21 requirement rows fully covered with a working, tested implementation.
- **Partially covered:** 0.
- **Missing:** 0.

P1-R09 (distributor order momentum) and P1-R21 (replenishment frequency) were
the two gaps identified in the prior review pass. Both were closed in this
pass: P1-R09 now has a dedicated isolated unit test (`test_23`) that varies
only `distributor_order_qty` while holding flu and promo signals at zero, and
P1-R21 was added as a small, additive field (`replenishment_cycle_days`,
`estimated_replenishments_per_year`) computed from numbers the engine already
produces — it does not alter the existing TRANSFER/REPLENISH/MONITOR decision
logic, which was re-verified unchanged (`test_24`, plus a full scenario
re-run).

This is not claimed as 100% requirement coverage of every conceivable interpretation
of the source documents — it is coverage of the requirements as extracted and listed
above, each with a cited implementation, endpoint, UI location, and test.
