#!/bin/sh
# Regenerate the synthetic P1 database fresh on every container start,
# then launch the API, respecting $PORT if the platform sets it.
set -e

echo "[entrypoint] generating synthetic P1 database..."
python3 app/data_gen.py

echo "[entrypoint] starting uvicorn on port ${PORT:-8000}..."
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
