FROM python:3.12-slim

WORKDIR /app

# Runtime-only dependencies (test tooling lives in requirements-dev.txt and
# is not needed in the deployed image).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# The SQLite database is generated at container START, not at build time.
# This keeps the image reproducible from source and means a fresh container
# always starts with a correctly-seeded database, even on platforms with an
# ephemeral filesystem. Regeneration takes ~1-2 seconds.
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENV PORT=8000

ENTRYPOINT ["./docker-entrypoint.sh"]
