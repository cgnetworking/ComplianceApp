#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${DATABASE_USER:?DATABASE_USER is required}"
: "${DATABASE_PASSWORD:?DATABASE_PASSWORD is required}"

python - <<'PY'
import os
import time
from urllib.parse import urlparse

import psycopg

database_url = os.environ["DATABASE_URL"]
database_user = os.environ["DATABASE_USER"]
database_password = os.environ["DATABASE_PASSWORD"]
max_attempts = int(os.environ.get("DATABASE_WAIT_MAX_ATTEMPTS", "30"))
delay_seconds = float(os.environ.get("DATABASE_WAIT_SECONDS", "2"))

parsed = urlparse(database_url)
host = parsed.hostname or "localhost"
port = parsed.port or 5432
dbname = parsed.path.lstrip("/")
if not dbname:
    raise SystemExit("DATABASE_URL must include a database name")

for attempt in range(1, max_attempts + 1):
    try:
        with psycopg.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=database_user,
            password=database_password,
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        print(f"Database is ready at {host}:{port}/{dbname}")
        break
    except Exception as exc:
        if attempt == max_attempts:
            raise SystemExit(
                f"Database did not become ready after {max_attempts} attempts: {exc}"
            ) from exc
        print(f"Waiting for database ({attempt}/{max_attempts}): {exc}")
        time.sleep(delay_seconds)
PY

python manage.py migrate --noinput

if [ "${COLLECTSTATIC_ON_START:-true}" = "true" ]; then
  python manage.py collectstatic --noinput
fi

exec gunicorn portal_backend.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --access-logfile - \
  --error-logfile -
