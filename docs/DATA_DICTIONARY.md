# Data Dictionary

All data is synthetic, generated deterministically by `backend/app/data_gen.py`
(seeded, so regenerating produces the same values). See that file's module
docstring for the full list of deliberately engineered scenarios.

## `skus`

| Column | Type | Description |
|---|---|---|
| sku_id | text (PK) | e.g. `MED-001` |
| name | text | Product name |
| category | text | Antibiotic / Analgesic / Chronic Care / Antihistamine / Supplement |
| criticality | text | Critical / High / Medium / Low — drives safety-stock z-score and priority weighting |
| unit_cost | real | ₹ cost per unit, used for expiry write-off cost |
| margin_per_unit | real | ₹ margin per unit, used for stockout cost |
| shelf_life_days | int | Full shelf life from manufacture, used to bound batch expiry generation |

## `dcs`

| Column | Type | Description |
|---|---|---|
| dc_id | text (PK) | e.g. `DC-METRO-MUM`, `DC-TIER2-HYD` |
| name | text | Display name |
| type | text | `Metro` or `Tier-2` |
| city | text | |
| capacity_units | int | Total storage capacity, used to gate transfer feasibility |
| supplier_lead_time_days | int | Inbound replenishment lead time from supplier |

## `transfer_lead_times`

| Column | Type | Description |
|---|---|---|
| source_dc | text | |
| dest_dc | text | |
| lead_time_days | int | Inter-DC transfer lead time (asymmetric, distance-driven) |

## `demand_history`

| Column | Type | Description |
|---|---|---|
| sku_id, dc_id | text | Composite identity |
| date | text (YYYY-MM-DD) | 180 days of history ending at `today` (2026-08-16) |
| actual_demand | int | Units demanded, incorporating weekly seasonality, promo uplift, flu multiplier, and noise |
| promo_active | int (0/1) | Whether a promotion was active that day |
| flu_signal | real | Flu ramp intensity that day (0 = inactive) |
| distributor_order_qty | int | Simulated distributor order lot, placed every ~5 days |

## `batches`

| Column | Type | Description |
|---|---|---|
| batch_id | text (PK) | e.g. `B00006` |
| sku_id, dc_id | text | |
| qty | int | Units in this batch |
| received_date | text | |
| expiry_date | text | |

## `promotions`

| Column | Type | Description |
|---|---|---|
| sku_id, dc_id | text | |
| start_date, end_date | text | |
| uplift_pct | real | Demand uplift fraction applied during the promo window |

## `forecast_cache`

Persisted cache of computed forecast payloads (JSON), keyed by `(sku_id,
dc_id)`. Written on startup by `services/cache.py`; read by the decision
engine for any request that isn't a live what-if.

## `monitoring_runs`

Snapshot rows used by the Monitoring screen's history view. Seeded on first
call to `/api/monitoring/history` with the actual computed network state.

## Financial assumptions (documented per the master requirement)

- **Stockout cost** = shortfall units × margin per unit × P(stockout), where
  P(stockout) is the stockout risk score (0-100) divided by 100, optionally
  scaled by the what-if `cost_weight_stockout` parameter.
- **Expiry cost** = FEFO-projected expiry-loss units × unit cost (full
  write-off value — no salvage value assumed).

These are documented modeling choices for a hackathon demo, not audited
financial figures.
