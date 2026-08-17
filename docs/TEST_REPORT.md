# Test Report

Run command: `cd backend && python3 -m pytest tests/test_p1.py -v`
Raw output: `docs/TEST_REPORT_RAW.txt`

## Result: **25 passed, 0 failed, 0 skipped** (~9-14s depending on environment)

| # | Test | Verifies | Result |
|---|---|---|---|
| 1 | test_01_healthy_sku_monitors | Healthy SKU → MONITOR, low stockout risk | PASSED |
| 2 | test_02_flu_signal_increases_sensed_demand | Flu +60% override genuinely raises sensed demand ≥40% | PASSED |
| 3 | test_03_forecast_changes_between_baseline_and_sensed | Sensed ≠ baseline for an active-flu combo | PASSED |
| 4 | test_04_rop_increases_with_demand_and_lead_time | ROP responds to both demand and lead-time increases | PASSED |
| 5 | test_05_transfer_feasible_flu_shortage | Flu shortage scenario resolves to TRANSFER with a source and positive quantity | PASSED |
| 6 | test_06_transfer_infeasible_replenishes | Long-lead-time shortage resolves to REPLENISH, with real rejected network candidates on record | PASSED |
| 7 | test_07_replenish_quantity_positive_and_reasonable | REPLENISH quantity ≈ shortfall | PASSED |
| 8 | test_08_near_expiry_batch_creates_expiry_risk | Engineered near-expiry batch produces expiry_risk_score > 0 and real projected loss | PASSED |
| 9 | test_09_fefo_orders_batches_by_expiry_ascending | FEFO allocation list is sorted earliest-expiry-first | PASSED |
| 10 | test_10_chronic_understock_flagged | Chronic understock SKU/DC shows stock below ROP and a corrective action | PASSED |
| 11 | test_11_priority_and_review_cadence_present | Priority, review cadence, and escalation text are all populated | PASSED |
| 12 | test_12_cost_weighting_changes_cost_estimate | Higher cost_weight_stockout produces a higher cost estimate | PASSED |
| 13 | test_13_what_if_demand_increase_reduces_expiry_loss | Boosting demand reduces projected expiry loss (faster FEFO consumption) | PASSED |
| 14 | test_14_what_if_demand_change_recalculates_forecast_and_rop | Demand override propagates through forecast → ROP | PASSED |
| 15 | test_15_what_if_lead_time_change_recalculates_rop | Lead-time override propagates through to ROP, and lead time itself reflects the delta | PASSED |
| 16 | test_16_network_health_endpoint_reflects_real_data | /network-health evaluates all 30 combos, action counts sum correctly | PASSED |
| 17 | test_17_capacity_headroom_considered_in_network_search | Every network candidate reports a real (non-null) capacity headroom figure | PASSED |
| 18 | test_18_forecast_metrics_are_computed_not_hardcoded | Two different SKU/DC combos produce different holdout metrics | PASSED |
| 19 | test_19_recommendation_completeness | WHAT/HOW MUCH/WHERE/WHY/REVIEW/ESCALATION all present in payload | PASSED |
| 20 | test_20_api_rejects_invalid_sku | Invalid SKU or DC → 422, not a crash | PASSED |
| 20b | test_20b_api_rejects_invalid_what_if_payload | Out-of-range what-if payload → 422 | PASSED |
| 21 | test_21_all_core_endpoints_return_200 | Every screen-supporting endpoint returns 200 | PASSED |
| 22 | test_22_what_if_endpoint_full_flow | Full what-if round trip via the actual HTTP endpoint, before/after values differ as expected | PASSED |
| 23 | test_23_distributor_order_momentum_affects_sensing_isolated | **New.** Isolates the distributor-momentum sensing component (flu=0, promo=0 held constant) and proves higher/lower distributor orders relative to demand genuinely raise/lower the sensing multiplier, with the component correctly bounded | PASSED |
| 24 | test_24_replenishment_frequency_present_and_consistent | **New.** Proves the newly-added replenishment-frequency fields are present for TRANSFER, REPLENISH, and MONITOR decisions, are numerically consistent with quantity/demand rate, and that adding them did not change the existing action/quantity/timing decision outputs | PASSED |

## What is intentionally *not* claimed

- These tests exercise the backend decision engine and API. They do **not**
  include automated frontend/browser tests (no headless-browser test runner
  was set up); frontend correctness was verified by a clean production build
  (`npm run build`), a lint pass (`oxlint`, 0 errors / 5 minor warnings), and
  manual verification that every page's module resolves and every backend
  endpoint the frontend calls returns 200 (see `docs/API_DOCUMENTATION.md` and
  the endpoint list in `test_21`).
- No load/stress testing was performed — only the response-time benchmark in
  `docs/PERFORMANCE.md`.
