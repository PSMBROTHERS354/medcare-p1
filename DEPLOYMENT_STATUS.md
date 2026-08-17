# Deployment Status

Generated after the final deployment-preparation pass on the existing P1
project. Every line below reflects something actually run and observed in
this session — not an assumption.

```
DEPLOYMENT READY:        YES  (manual deploy, using DEPLOYMENT.md — see caveats below)
LOCAL PRODUCTION BUILD:  PASS
BACKEND START:           PASS
FRONTEND BUILD:          PASS
API INTEGRATION:         PASS
CORS:                    PASS
25 TESTS:                PASS  (23 original + 2 added in this pass: distributor-momentum isolation, replenishment-frequency)
DOCKER BUILD:            NOT TESTABLE  (no Docker daemon available in this environment)
LIVE DEPLOYMENT:         NOT DEPLOYED  (no network access to hosting platforms from here)
```

## Evidence for each line

**LOCAL PRODUCTION BUILD — PASS**
Backend dependencies installed from `requirements.txt` only (production
subset, no pytest/httpx). `python3 app/data_gen.py` regenerated the SQLite
database cleanly. Frontend: `npm run build` produced `dist/` with 0 build
errors on two separate runs (default dev URL, and a custom production URL
passed via env var).

**BACKEND START — PASS**
Started with the exact documented command,
`python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"`,
with `PORT` and `ALLOWED_ORIGINS` set via environment variables (not
hardcoded). `GET /api/health` responded with
`"forecast_cache_size": 30` and the correctly-parsed `allowed_origins` list.

**FRONTEND BUILD — PASS**
`npm run build` succeeded from a clean `node_modules` install. Verified the
built JS bundle: building with `VITE_API_BASE_URL=https://medcare-p1-api.example-deploy.com`
produced a bundle containing that exact string and **zero** occurrences of
`localhost:8000` — confirming the API URL is genuinely configurable at build
time and nothing is hardcoded. `oxlint` reported 0 errors (5 pre-existing
minor warnings, unrelated to these changes).

**API INTEGRATION — PASS**
The production frontend build was served locally with `serve -s dist -l 4173`
(simulating real static hosting). All 15 endpoints used by the four screens
(`/skus`, `/dcs`, `/scenarios`, `/network-health`, `/network-map`,
`/attention-queue`, `/monitoring/metrics`, `/monitoring/history`,
`/forecast/...`, `/inventory/...`, `/recommendation/...` ×3, `/network/...`,
`POST /what-if`) were called with `Origin: http://localhost:4173` and all
returned `200`.

**CORS — PASS**
Verified directly with curl against the running backend:
- `Origin: http://localhost:4173` (an allowed origin) → response includes
  `access-control-allow-origin: http://localhost:4173`.
- `Origin: https://evil.example.com` (not in `ALLOWED_ORIGINS`) → no
  CORS header returned, confirming the wildcard (`*`) has been removed and
  the allowlist is actually enforced.

**25 TESTS — PASS**
`python3 -m pytest tests/test_p1.py -v` → `25 passed, 0 failed, 0 skipped`
(23 from the prior pass + 2 added in this final technical check: an isolated
test for P1-R09 distributor-order-momentum, and a test for the newly-added
replenishment-frequency fields). Run multiple times in this session,
including once immediately after a clean `medcare.db` regeneration. Full
output in `docs/TEST_REPORT.md` / `docs/TEST_REPORT_RAW.txt`.

**P1 demo scenarios re-verified after all deployment changes:**
| Scenario | SKU / DC | Result |
|---|---|---|
| Flu shortage | MED-001 / DC-TIER2-HYD | `action=TRANSFER`, stockout risk 100 |
| Long-lead-time shortage | MED-003 / DC-TIER2-PAT | `action=REPLENISH`, stockout risk 100 |
| Healthy SKU | MED-004 / DC-METRO-MUM | `action=MONITOR`, risk 0 |
| Near-expiry excess | MED-001 / DC-METRO-CHN | `action=MONITOR`, expiry risk 22.2 (correctly flagged, non-zero) |

**DOCKER BUILD — NOT TESTABLE**
`docker` is not installed in this build environment (`docker --version` →
command not found). `backend/Dockerfile`, `frontend/Dockerfile`, and
`docker-compose.yml` have been rewritten and manually reviewed for
correctness (multi-stage build, `$PORT` handling, build-arg for
`VITE_API_BASE_URL`, entrypoint script that regenerates the database on every
container start) but **have not been built or run**. This is stated
explicitly rather than assumed to work — please run `docker compose up --build`
yourself and treat that as the first real test of these files.

**LIVE DEPLOYMENT — NOT DEPLOYED**
This environment's outbound network access is restricted to a fixed
allowlist (package registries, GitHub, the Anthropic API) and does not
include hosting-platform domains (Render, Railway, Vercel, Netlify, Fly.io,
etc.). No deployment was attempted, and none is claimed. `DEPLOYMENT.md`
contains the exact manual steps for a Render (backend) + Vercel (frontend)
deployment, which is the recommended platform pair for this architecture.

## What "DEPLOYMENT READY: YES" means here, precisely

It means: every step that does *not* require Docker or a hosting-platform
account has been executed and verified in this session — clean-environment
backend start, production frontend build with a genuinely configurable API
URL, CORS restricted to a real allowlist, full API integration, and all 23
tests. It does **not** mean the project is live on the internet, and it does
**not** mean the Docker files have been proven to build — both of those
require access this environment doesn't have, and are called out above
rather than glossed over.
