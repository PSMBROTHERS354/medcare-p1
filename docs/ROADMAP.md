# Development Roadmap

Phases as specified, with realistic estimates and actual status for this build.

| Phase | Description | Estimate | Status |
|---|---|---|---|
| 1 | Requirement analysis (extract P1-R01…R20 from official docs) | 0.5 day | Done — see `REQUIREMENT_TRACEABILITY.md` |
| 2 | Data generation / modeling (schema + engineered scenarios) | 1 day | Done — `data_gen.py`, 6 SKUs × 5 DCs, 5,400 demand rows, 138 batches |
| 3 | Demand sensing + forecasting (Holt-Winters, holdout eval, sensing multiplier) | 1 day | Done — `forecasting.py` |
| 4 | Inventory / expiry / FEFO | 0.5 day | Done — `inventory.py` |
| 5 | ROP / risk / root cause | 1 day | Done — `rop.py`, `risk.py`, `root_cause.py` |
| 6 | Network decision engine (search, transfer feasibility, orchestrator) | 1 day | Done — `network.py`, `decision.py` |
| 7 | FastAPI (endpoints, validation, caching) | 1 day | Done — `main.py`, `cache.py` |
| 8 | Frontend / UI (4 screens, design system) | 1.5 days | Done — `frontend/src/pages/*` |
| 9 | Testing / performance | 0.5 day | Done — 23/23 tests passing, benchmarks recorded |
| 10 | Documentation / deployment | 0.5 day | Done — this documentation set, Docker config (untested against a live daemon) |

**Total realistic estimate for a from-scratch build: ~8 person-days** for one
engineer working solo across all roles (architecture, backend, forecasting,
frontend, QA, docs) — consistent with a focused hackathon sprint rather than a
multi-week production effort.

## What would come next (beyond P1 scope)

- Real data ingestion (replacing `data_gen.py` with actual ERP/distributor
  feeds) — would require a proper ETL layer and data validation beyond what's
  built here.
- A real forecast-retraining schedule (currently forecasts are computed once
  at process startup; a production system would refresh on a cadence or on
  new-data triggers).
- Multi-writer inventory updates (would justify moving from SQLite to
  PostgreSQL, per `ARCHITECTURE_ALTERNATIVES.md`).
- Automated frontend/browser test coverage (Playwright or similar).
