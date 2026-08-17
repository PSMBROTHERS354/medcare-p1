# Deployment Guide

## Architecture

```
Frontend (React/Vite, static build)  →  Backend API (FastAPI/uvicorn)  →  SQLite + forecast cache
        served as static files             single process, single port      file on the backend's
        (serve / any static host)          reads ALLOWED_ORIGINS + PORT     own filesystem, rebuilt
                                            from environment                on every container start
```

This is the preferred architecture from the brief (**Frontend → Backend API →
SQLite/data/cache**) and it fits this project well — no change was made to it.
The backend is a single FastAPI process; SQLite plus the in-process/persisted
forecast cache live entirely inside that process's container/filesystem. There
is no separate database service to provision.

**Why not something else:** the dataset is small (6 SKUs × 5 DCs, ~5,400
demand rows), single-writer, and regenerated deterministically from
`data_gen.py` — there's no multi-writer or high-availability requirement that
would justify a managed database service for this hackathon deliverable. See
`docs/ARCHITECTURE_ALTERNATIVES.md` for the SQLite-vs-PostgreSQL discussion.

## Prerequisites

- Python 3.12 (backend)
- Node.js 22 / npm (frontend)
- No external services, API keys, or secrets are required — all data is
  synthetic and generated locally.

## Environment variables

### Backend

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port uvicorn listens on. Most PaaS platforms (Render, Railway, Heroku, Cloud Run) inject this automatically. |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173` | Comma-separated exact origins allowed via CORS. **Must be set to the real deployed frontend URL in production** — see CORS section below. |

See `backend/.env.example`.

### Frontend

| Variable | Default (`.env`) | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend root URL. The `/api` path prefix is appended automatically by `src/api/client.js`, so this can be set with or without a trailing `/api`. |

See `frontend/.env` (development default) and
`frontend/.env.production.example` (copy to `.env.production` before a real
build, or set the equivalent variable in your hosting platform's dashboard).

**Important Vite constraint:** `VITE_*` variables are baked into the built JS
bundle at **build time**, not read at container/server runtime. If you change
the backend URL, you must rebuild the frontend — there is no way around this
for a static Vite SPA. This was verified directly in this session: building
with `VITE_API_BASE_URL=https://medcare-p1-api.example-deploy.com` produced a
bundle containing that exact string and zero occurrences of `localhost:8000`.

## Backend setup (local)

```bash
cd backend
pip install -r requirements.txt          # production dependencies only
python3 app/data_gen.py                  # generates medcare.db (synthetic, deterministic)
python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

For local development, also install test dependencies:
```bash
pip install -r requirements.txt -r requirements-dev.txt
python3 -m pytest tests/test_p1.py -v
```

Verify: `curl http://localhost:8000/api/health` should return
`"forecast_cache_size": 30` and an `allowed_origins` list.

## Frontend setup (local)

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173, reads VITE_API_BASE_URL from .env
```

## Local production run (no Docker)

This exact sequence was run and verified in this session:

```bash
# Backend — production dependencies only, documented start command
cd backend
pip install -r requirements.txt
python3 app/data_gen.py
ALLOWED_ORIGINS="http://localhost:4173" PORT=8000 \
  python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

# Frontend — real production build, served as static files (not `vite dev`)
cd frontend
npm install
npm run build           # uses VITE_API_BASE_URL from .env or the shell environment
npx serve -s dist -l 4173
```

Then open `http://localhost:4173`. This mirrors what a real deployment looks
like: a static frontend build talking to a separately-running API process,
with CORS enforced between the two.

## Docker run

`backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml` are
provided and have been reviewed line-by-line for correctness, but **Docker is
not available in the sandbox this project was built in, so `docker build` /
`docker compose up` have not actually been executed.** See
`DEPLOYMENT_STATUS.md` for the precise claim. If you have Docker locally:

```bash
docker compose up --build
```

This builds the backend image (installs `requirements.txt`, regenerates the
SQLite database on every container start via `docker-entrypoint.sh`, listens
on `$PORT`) and the frontend image (builds the Vite app with
`--build-arg VITE_API_BASE_URL=http://localhost:8000` baked in, serves the
static `dist/` folder with `serve` on `$PORT`).

To point the Dockerized frontend at a different backend, rebuild with a
different build arg (this is the Vite build-time constraint mentioned above):

```bash
docker build --build-arg VITE_API_BASE_URL=https://your-backend-url -t medcare-frontend ./frontend
```

**Please validate `docker compose up --build` yourself before relying on it**
— it has been reviewed, not run, in this environment.

## Deployment instructions (recommended platforms)

I cannot deploy directly from this environment — outbound network access here
is restricted to a fixed allowlist (package registries, GitHub, the Anthropic
API) and does not include hosting-platform domains like Render, Railway,
Vercel, Netlify, or Fly.io. Deployment must be done manually. Recommended
split:

### Backend → Render (or Railway)

Both support a plain Python/uvicorn web service without Docker, using the
included `backend/Procfile`:

1. Push this repository to GitHub.
2. On Render: New → Web Service → connect the repo, root directory
   `backend`, build command `pip install -r requirements.txt`, start command
   `python3 app/data_gen.py && python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   (Render sets `$PORT` automatically).
3. Set the `ALLOWED_ORIGINS` environment variable to your frontend's URL once
   you know it (step below) — you can update this after the frontend is
   deployed and redeploy/restart the backend service, no rebuild needed since
   it's read at process start, not baked in.
4. Note the resulting URL, e.g. `https://medcare-p1-api.onrender.com`.

### Frontend → Vercel (or Netlify)

1. On Vercel: New Project → import the same repo, root directory `frontend`,
   framework preset "Vite".
2. Add environment variable `VITE_API_BASE_URL` = the backend URL from above
   (e.g. `https://medcare-p1-api.onrender.com`).
3. Deploy. Vercel runs `npm run build` with that env var present, so it gets
   baked into the bundle correctly.
4. Note the resulting URL, e.g. `https://medcare-p1.vercel.app`.
5. Go back to the Render backend and set `ALLOWED_ORIGINS` to that exact
   Vercel URL, then restart the backend service.

### Why this split

Render/Railway run a real long-lived Python process well (needed for the
in-memory forecast cache warmed at startup); Vercel/Netlify are purpose-built
for static SPA hosting and handle the Vite build-time env var injection
cleanly through their dashboard. A single combined host is also possible
(e.g. both on Render as two services, or the Docker Compose setup on any
VM/Docker-capable host) — this split is simply the lowest-friction option for
someone deploying this manually for the first time.

## CORS configuration

`ALLOWED_ORIGINS` on the backend must contain the **exact** frontend origin
(scheme + host + port, no trailing slash, no path). Verified in this session:

```
$ curl -H "Origin: http://localhost:4173" -I http://localhost:8000/api/health
< access-control-allow-origin: http://localhost:4173      # allowed origin: header present

$ curl -H "Origin: https://evil.example.com" -I http://localhost:8000/api/health
                                                             # disallowed origin: no header, request blocked by browser
```

For a real deployment, set `ALLOWED_ORIGINS` to your Vercel/Netlify URL (and
keep the local dev origins in the list too if you want to keep testing
locally against the deployed backend).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Frontend shows network errors / blank data | `VITE_API_BASE_URL` wrong or backend not reachable | Check `.env` / platform env var, rebuild frontend if changed |
| Browser console shows a CORS error | Frontend origin not in backend's `ALLOWED_ORIGINS` | Add the exact origin, restart backend (no rebuild needed) |
| `GET /api/health` returns `forecast_cache_size: 0` briefly after start | Cache still warming | Wait ~5-8s after backend start before hitting bulk endpoints |
| Frontend still hits `localhost:8000` after deploying | Vite bundle built before the env var was set | Rebuild the frontend — `VITE_*` vars are baked in at build time, not read at runtime |
| `422` errors from the API | Invalid SKU/DC id or out-of-range what-if input | This is intentional input validation, not a bug — check `docs/API_DOCUMENTATION.md` for valid values |
| Backend fails to start with a missing-module error | Only `requirements.txt` (prod) installed but trying to run `pytest` | Also install `requirements-dev.txt` for local dev/testing |

## Known deployment limitations

- Docker build/run has been reviewed but not executed (no Docker in the
  build environment) — validate `docker compose up --build` yourself before
  relying on it for judging.
- No live deployment has been performed from this environment — network
  access here does not reach hosting-platform domains. The steps above are
  accurate and specific, but manual execution by you is required.
- The SQLite database is regenerated fresh on every backend process start
  (both locally and in the documented Docker/Procfile flows). This is
  intentional — it guarantees the demo data is always in its known-good,
  deterministic state — but it also means there is no persistent
  user-modifiable data between restarts. That's correct for a demo, not for a
  real production inventory system.
- `ALLOWED_ORIGINS` must be updated (and the backend restarted — not
  rebuilt) whenever the frontend's deployed URL changes.
- No CI/CD pipeline exists. No automated deployment on push.
