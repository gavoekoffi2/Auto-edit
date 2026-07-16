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

# Dépendances binaires OBLIGATOIRES: échec franc au démarrage plutôt qu'un
# rendu qui meurt en plein job (ou une image construite sans ffmpeg).
for bin in ffmpeg ffprobe; do
  if ! command -v "$bin" >/dev/null; then
    echo "[entrypoint] FATAL: dépendance obligatoire absente: $bin" >&2
    exit 1
  fi
done
python - <<'PYCHECK' || exit 1
import importlib, sys
for mod in ("cv2", "yt_dlp", "whisper", "PIL"):
    try:
        importlib.import_module(mod)
    except Exception as exc:
        print(f"[entrypoint] FATAL: module Python obligatoire absent: {mod} ({exc})",
              file=sys.stderr)
        sys.exit(1)
PYCHECK
if ! fc-list 2>/dev/null | grep -qi "poppins"; then
  echo "[entrypoint] WARNING: polices de sous-titres absentes de fontconfig" >&2
fi

echo "[entrypoint] Starting application..."
exec "$@"
