#!/bin/bash
set -euo pipefail

# Attend que Postgres soit pret (max ~60s)
if [ -n "${DATABASE_URL_SYNC:-}" ]; then
  echo "[entrypoint] Waiting for Postgres..."
  for i in {1..30}; do
    if python -c "
import os, sys
from sqlalchemy import create_engine, text
try:
    e = create_engine(os.environ['DATABASE_URL_SYNC'])
    with e.connect() as c:
        c.execute(text('SELECT 1'))
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
      echo "[entrypoint] Postgres is ready"
      break
    fi
    sleep 2
  done
fi

# Migrations Alembic — FAIL FAST si elles plantent (pas de fallback silencieux)
echo "[entrypoint] Running database migrations..."
alembic upgrade head

# Avertissement explicite si on tourne en prod sans email provider serieux
if [ "${APP_ENV:-development}" = "production" ]; then
  if [ "${EMAIL_PROVIDER:-console}" = "console" ]; then
    echo "[entrypoint] WARNING: APP_ENV=production with EMAIL_PROVIDER=console — password reset emails will only be logged, not sent."
  fi
  if [ -z "${FEDAPAY_SECRET_KEY:-}" ]; then
    echo "[entrypoint] WARNING: APP_ENV=production without FEDAPAY_SECRET_KEY — webhooks will be rejected."
  fi
fi

echo "[entrypoint] Starting application..."
exec "$@"
