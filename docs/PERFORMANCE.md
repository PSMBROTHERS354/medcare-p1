# Performance Benchmarks

All timings measured locally against the running FastAPI dev server
(`uvicorn`, single worker, no reverse proxy), 3 runs each, after the forecast
cache had been warmed on startup.

| Endpoint | What it does | Before caching | After caching (3 runs) |
|---|---|---|---|
| `GET /api/recommendation/{sku}/{dc}` | Single SKU/DC full decision | ~500-900ms (uncached fit) | 37.0ms / 32.0ms / 31.5ms |
| `GET /api/network-health` | Evaluates all 30 combos | ~14,000ms | 416.2ms / 415.6ms / 414.0ms |
| `GET /api/network-map` | Evaluates all 30 combos + edges | ~14,000ms | 403.0ms / 405.9ms / 448.8ms |
| `GET /api/attention-queue` | Evaluates all 30 combos | ~14,000ms | 408.5ms / 408.0ms / 410.1ms |
| `POST /api/what-if` | Live recompute for 1 combo + network search (~5 live fits) | N/A (always live) | 1152.3ms / 1139.7ms / 1140.5ms |

"Before caching" figures are from ad-hoc timing during development, before
`services/cache.py` was introduced (see `docs/ARCHITECTURE.md` → Performance
approach for how this was found and fixed).

## Why what-if is still ~1.1s

A what-if request needs one live Holt-Winters fit for the target SKU/DC (to
apply the override), plus the network search re-evaluates forecasts for up to
4 sister DCs if stockout risk crosses the action threshold — that's up to 5
live fits in the worst case, each taking roughly 150-220ms. This is
acceptable for an interactive single-scenario exploration tool (the person is
actively watching one slider), but would not be acceptable if called in a
loop across all 30 combinations — which is exactly why the bulk endpoints use
the cache instead of what-if's live path.

## Not measured

- Concurrent-user load (this was tested single-request, sequentially).
- Cold-start time including `data_gen.py` (database generation) — measured
  separately at ~1-2 seconds for the full 5,400-row demand history + 138
  batches.
- Frontend render performance / Lighthouse scores.
