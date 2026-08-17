# Known Limitations

Stated honestly, per the master requirement not to claim "100% complete,"
"production ready," or "real-time" unless actually true.

## Data

- All data is synthetic. It is deliberately engineered to demonstrate the P1
  scenarios (see `data_gen.py`), which means it is realistic in *shape* but
  not sourced from any real MedCare Pharma system.
- 180 days of history and 6 SKUs / 5 DCs is enough to demonstrate the problem
  convincingly but is a small fraction of what a real pharma distribution
  network would carry (hundreds of SKUs, dozens of DCs, years of history).

## Forecasting

- Holt-Winters with weekly seasonality does not capture longer seasonal
  cycles (e.g. annual flu seasonality) beyond what's explicitly injected as a
  flu signal. A production system with multi-year history could add yearly
  seasonality terms.
- The holdout window (14 days) is short. With more history, a longer or
  rolling-origin holdout would give a more robust accuracy estimate.
- The demand-sensing multiplier's coefficients (flu ramp weighting, +10%
  promo flat bump, momentum bounds) are hand-set, documented assumptions —
  not fit from data, since no historical "ground truth sensing outcome"
  exists to fit against in a synthetic dataset.

## Decision engine

- The stockout-risk action threshold (20/100) and the transfer-feasibility
  lead-time threshold (≤4 days) are documented, reasonable defaults, not
  values derived from an optimization process.
- Cost-of-inaction financial assumptions (documented in `DATA_DICTIONARY.md`)
  are illustrative, not audited.

## Performance

- Benchmarked only as a single sequential user against a local `uvicorn` dev
  server (see `PERFORMANCE.md`). No load testing was performed.
- The forecast cache is warmed once at process startup. In a long-running
  production deployment, a scheduled refresh job would be needed; that job is
  not implemented here.

## Testing

- 23 backend/API tests pass with real assertions (see `TEST_REPORT.md`). There
  is no automated browser-level (Playwright/Cypress) test suite for the
  frontend; frontend correctness was verified via a clean production build,
  linting, and manual endpoint/module resolution checks.

## Deployment

- `docker-compose.yml` and both Dockerfiles are written and reviewed but have
  **not** been run end-to-end against a live Docker daemon in this build
  environment (no Docker available in the sandbox used to build this). See
  `DEPLOYMENT_STATUS.md` for the exact, current, verified status of every
  deployment concern (CORS, production build, backend start, API
  integration, and test suite have all been verified; Docker build and live
  deployment have not, and are explicitly marked as such rather than
  assumed).
- No live deployment exists. `DEPLOYMENT.md` documents the exact manual steps
  for a Render (backend) + Vercel (frontend) deployment.
- No CI/CD pipeline exists. No automated deployment on push.
- CORS is now environment-configurable (`ALLOWED_ORIGINS`) rather than a
  wildcard — this was tightened during deployment preparation and verified
  with both an allowed and a disallowed origin.

## Scope

- This is P1 only. No E1 functionality, alerts, transaction simulator, or
  P1→E1 integration exists in this codebase, per the master scope rule.
