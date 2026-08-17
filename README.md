# MedCare Pharma — P1: Demand Sensing & Replenishment Planning

An explainable demand-sensing and replenishment decision-support system built for
the Cognizant hackathon **P1 use case only** (Demand Planning & Replenishment).
This repository does **not** implement E1 or any P1↔E1 integration — it is
independently runnable and independently demonstrable.

## The business story

> During a flu-season demand surge, critical SKUs can become unavailable in
> Tier-2 DCs while Metro DCs may have excess near-expiry inventory.

The system senses the demand shift, recalculates the forecast, recalculates the
dynamic reorder point, evaluates stockout and expiry risk, explains the root
cause, searches the network for usable excess before ever recommending a
supplier replenishment, checks transfer feasibility (expiry, lead time,
capacity), and emits one of **TRANSFER / REPLENISH / MONITOR** with quantity,
timing, priority, review cadence, and escalation guidance.

## Architecture

```
Frontend (React + Vite)
    ↓ REST (fetch)
FastAPI (backend/app/main.py)
    ↓
Decision Services (backend/app/services/)
    ├── demand sensing (forecasting.py: sensing_multiplier)
    ├── forecasting (forecasting.py: Holt-Winters + holdout eval)
    ├── inventory position (inventory.py)
    ├── FEFO / expiry risk (inventory.py)
    ├── dynamic ROP (rop.py)
    ├── risk engine (risk.py)
    ├── root cause (root_cause.py)
    ├── network search / transfer feasibility (network.py)
    ├── cost of inaction / priority (cost.py)
    └── decision orchestrator (decision.py)
    ↓
SQLite (backend/medcare.db) + persisted forecast cache (services/cache.py)
```

See `docs/ARCHITECTURE.md` for the full component diagram and alternatives
considered.

## Repository layout

```
medcare-p1/
├── backend/
│   ├── app/
│   │   ├── data_gen.py       # synthetic data generator (reproducible, seeded)
│   │   ├── db.py             # SQLite access helpers
│   │   ├── main.py           # FastAPI app + all endpoints
│   │   └── services/         # the 9 decision-engine modules
│   ├── tests/test_p1.py      # 23 automated tests, real assertions
│   └── medcare.db            # generated on first run of data_gen.py
├── frontend/
│   ├── src/pages/            # the 4 P1 screens
│   ├── src/components/       # Shell, NetworkRiskMap, shared widgets
│   └── src/api/client.js     # typed fetch wrapper around the FastAPI backend
└── docs/                     # this documentation set
```

## Running it

### Backend

```bash
cd backend
pip install -r requirements.txt              # production dependencies
python3 app/data_gen.py        # builds medcare.db with engineered scenarios
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For local development (adds test tooling):
```bash
pip install -r requirements.txt -r requirements-dev.txt
```

The API is now live at `http://localhost:8000/api` (see `/api/health`).
On startup the app pre-computes and caches forecasts for all 30 SKU × DC
combinations (~a few seconds) so subsequent network-wide requests are fast.

CORS is environment-configurable via `ALLOWED_ORIGINS` (comma-separated exact
origins) — see `backend/.env.example` and `DEPLOYMENT.md`.

### Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173, proxies to the API via VITE_API_BASE_URL
```

`frontend/.env` sets `VITE_API_BASE_URL=http://localhost:8000/api` by default.

### Production build

```bash
cd frontend
npm run build           # outputs static assets to frontend/dist
npm run preview         # serve the production build locally
```

### Tests

```bash
cd backend
python3 -m pytest tests/test_p1.py -v
```

23/23 tests pass as of the last verified run — see `docs/TEST_REPORT.md` for the
full output.

### Docker

A `docker-compose.yml` is provided for local container-based startup (backend +
frontend). It has been reviewed but **not run against a live Docker daemon**
(unavailable in the environment this project was built in) — see
`DEPLOYMENT_STATUS.md` for the precise, verified status of every deployment
concern, and `DEPLOYMENT.md` for full setup, environment variables, CORS
configuration, and manual deployment steps (Render + Vercel recommended).

## Screens

1. **Command Center** — "What needs attention now?" Network health, forecast
   accuracy, the supply network risk map, and the critical action queue.
2. **SKU / DC Intelligence** — "Why is this SKU at risk?" Forecast comparison,
   inventory/ROP, batch-level expiry, root cause, network alternatives, and the
   full WHAT/HOW MUCH/WHERE/WHEN/WHY/REVIEW/ESCALATION explanation.
3. **Decision Studio** — "What happens if conditions change?" Interactive
   what-if simulator (demand slider, flu toggle, lead-time control, cost
   weighting) with a genuine before/after recalculation.
4. **Monitoring** — "Is the network improving?" Action distribution, priority
   breakdown, and the full current action history.

## What this is honestly not

- Not a production deployment. It has been run locally and tested locally; see
  `docs/KNOWN_LIMITATIONS.md`.
- Not real-time in the strict sense — the forecast cache is warmed on startup
  and the what-if simulator computes live on demand, but there is no streaming
  or push-based update mechanism.
- Not using deep learning for forecasting by design — see
  `docs/ARCHITECTURE_ALTERNATIVES.md` for why Holt-Winters was chosen for this
  data volume and explainability requirement.
