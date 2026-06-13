#!/usr/bin/env bash
set -euo pipefail

# AutoEdit production deploy script.
# Usage on the VPS:
#   cd /root/projects/Auto-edit
#   BACKEND_DOMAIN=autoedit.srv1305401.hstgr.cloud FRONTEND_ORIGIN=https://your-netlify-site.netlify.app ./deploy.sh
#
# Requirements: Docker + Docker Compose plugin. On this VPS, the global Traefik
# reverse proxy owns ports 80/443, so deploy.sh automatically layers
# docker-compose.traefik.yml when it exists and does NOT start the legacy Caddy
# service unless explicitly profiled.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Stable project name preserves existing production volumes/containers
# (autoeditprod_postgres_data, autoeditprod_uploads_data). Without this,
# Docker derives "auto-edit" from the directory and creates a fresh duplicate
# stack that can race the old Traefik route and hide the deployed code.
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-autoeditprod}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT_NAME" -f docker-compose.yml -f docker-compose.prod.yml)
# Production on this VPS is behind the already-running global Traefik proxy.
# Without this override, docker-compose.prod.yml still leaves nginx/caddy active
# while frontend is profiled out, causing: service "nginx" depends on undefined
# service "frontend": invalid compose project.
if [ -f docker-compose.traefik.yml ]; then
  COMPOSE+=( -f docker-compose.traefik.yml )
fi
ENV_FILE="$ROOT_DIR/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "[deploy] ERROR: docker is not installed." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "[deploy] ERROR: docker compose plugin is not installed." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  cp .env.example "$ENV_FILE"
  ENV_CREATED=1
  echo "[deploy] Created .env from .env.example. Fill third-party keys after first deploy if needed."
else
  ENV_CREATED=0
fi
chmod 600 "$ENV_FILE"
export ENV_CREATED

python3 - <<'PY'
from pathlib import Path
import os, secrets, re, sys
p = Path('.env')
text = p.read_text()

def set_key(src: str, key: str, value: str) -> str:
    pattern = re.compile(rf'^{re.escape(key)}=.*$', re.M)
    line = f'{key}={value}'
    if pattern.search(src):
        return pattern.sub(line, src)
    return src.rstrip() + '\n' + line + '\n'

def get_key(src: str, key: str) -> str:
    m = re.search(rf'^{re.escape(key)}=(.*)$', src, re.M)
    return m.group(1).strip() if m else ''

# Production defaults that are safe to write automatically.
text = set_key(text, 'APP_ENV', 'production')
text = set_key(text, 'PIPELINE_VERSION', os.environ.get('PIPELINE_VERSION', get_key(text, 'PIPELINE_VERSION') or 'v2'))
text = set_key(text, 'VIDEO_RENDERER', os.environ.get('VIDEO_RENDERER', get_key(text, 'VIDEO_RENDERER') or 'ffmpeg'))
text = set_key(text, 'WHISPER_MODEL', os.environ.get('WHISPER_MODEL', get_key(text, 'WHISPER_MODEL') or 'base'))
text = set_key(text, 'CELERY_CONCURRENCY', os.environ.get('CELERY_CONCURRENCY', get_key(text, 'CELERY_CONCURRENCY') or '2'))

backend_domain = os.environ.get('BACKEND_DOMAIN') or get_key(text, 'BACKEND_DOMAIN') or ''
if backend_domain:
    text = set_key(text, 'BACKEND_DOMAIN', backend_domain)
    text = set_key(text, 'PUBLIC_APP_URL', f'https://{backend_domain}')
    # Netlify origin must be added manually if known: CORS_ORIGINS=https://your-netlify.app,https://custom-frontend.com

if os.environ.get('TLS_EMAIL'):
    text = set_key(text, 'TLS_EMAIL', os.environ['TLS_EMAIL'])

frontend_origin = os.environ.get('FRONTEND_ORIGIN') or get_key(text, 'FRONTEND_ORIGIN') or ''
if frontend_origin:
    text = set_key(text, 'FRONTEND_ORIGIN', frontend_origin)
    # CORS must contain origins only (scheme + host), no /api path.
    existing = [x.strip() for x in get_key(text, 'CORS_ORIGINS').split(',') if x.strip()]
    if frontend_origin not in existing:
        existing.append(frontend_origin)
    text = set_key(text, 'CORS_ORIGINS', ','.join(existing))

secret = get_key(text, 'SECRET_KEY')
if not secret or secret in {'change-me', 'dev-secret-key-change-in-production'} or secret.startswith('replace-me') or len(secret) < 32:
    text = set_key(text, 'SECRET_KEY', secrets.token_urlsafe(48))
    print('[deploy] Generated stable SECRET_KEY in .env (not printed).')

# Generate a strong Postgres password only on a brand-new .env. Do not rotate
# it later: an existing Postgres volume keeps the original DB password.
pg = get_key(text, 'POSTGRES_PASSWORD')
if os.environ.get('ENV_CREATED') == '1' and (not pg or pg in {'change-me-in-production', 'autoedit', 'password'}):
    text = set_key(text, 'POSTGRES_PASSWORD', secrets.token_urlsafe(32))
    print('[deploy] Generated POSTGRES_PASSWORD in .env (not printed).')
elif pg in {'change-me-in-production', 'autoedit', 'password'}:
    print('[deploy] WARNING: POSTGRES_PASSWORD still looks like a placeholder. Change it before real production traffic.')

p.write_text(text)
PY

set +u
# Load non-secret public deploy values for compose interpolation without printing them.
BACKEND_DOMAIN="${BACKEND_DOMAIN:-$(grep -E '^BACKEND_DOMAIN=' .env 2>/dev/null | tail -1 | cut -d= -f2-)}"
TLS_EMAIL="${TLS_EMAIL:-$(grep -E '^TLS_EMAIL=' .env 2>/dev/null | tail -1 | cut -d= -f2-)}"
set -u

if [ -z "${BACKEND_DOMAIN:-}" ] || [ "$BACKEND_DOMAIN" = "localhost" ]; then
  echo "[deploy] WARNING: BACKEND_DOMAIN is not set. HTTPS certificates need a real DNS name."
  echo "[deploy] Example: BACKEND_DOMAIN=srv1305401.hstgr.cloud TLS_EMAIL=you@example.com ./deploy.sh"
fi

# Build sequentially. Docker Compose/BuildKit on this VPS can fail parallel builds
# with "image ... already exists" when backend and worker share the same Dockerfile/context.
export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"

# Old failed deploys can leave backend/worker containers detached from the current
# Compose state; remove only stateless app containers before recreating them.
docker rm -f "${COMPOSE_PROJECT_NAME}-backend-1" "${COMPOSE_PROJECT_NAME}-worker-1" >/dev/null 2>&1 || true

# Build and start all services.
echo "[deploy] Building and starting AutoEdit production stack..."
"${COMPOSE[@]}" up -d --build

echo "[deploy] Services:"
"${COMPOSE[@]}" ps

# Health-check DIRECTEMENT le conteneur backend (port 8000 interne), pas via le
# proxy: sur ce VPS, Traefik possède 80/443 et redirige localhost HTTP->HTTPS
# (301), ce qui faisait lire un faux "Moved Permanently". On interroge donc le
# backend lui-même — c'est la vraie santé applicative.
echo "[deploy] Waiting for API health (backend container)..."
for i in {1..30}; do
  if "${COMPOSE[@]}" exec -T backend \
       curl -fsS --max-time 5 http://localhost:8000/api/health >/tmp/autoedit-health.json 2>/dev/null; then
    echo "[deploy] Backend health OK: $(cat /tmp/autoedit-health.json)"
    break
  fi
  sleep 2
  if [ "$i" = "30" ]; then
    echo "[deploy] ERROR: backend /api/health never became healthy" >&2
    "${COMPOSE[@]}" logs --tail=120 backend worker >&2 || true
    exit 1
  fi
done

# Janitor: purge les intermédiaires de rendu accumulés dans le volume uploads.
# Chaque montage écrivait des Go de ProRes .mov + passes mp4 jamais nettoyés;
# disque plein => ffmpeg meurt en plein encodage ("[Errno 32] Broken pipe").
# On supprime UNIQUEMENT les fichiers intermédiaires connus, jamais les vidéos
# sources ni les montages finaux (final_output.mp4 / final_montage_web.mp4).
echo "[deploy] Cleaning render intermediates in uploads volume..."
"${COMPOSE[@]}" exec -T backend sh -c '
  set -e
  cd /app/uploads 2>/dev/null || exit 0
  for d in clips_graded animations motion_clips broll_clips sfx; do
    find . -path "*/output/*" -type d -name "$d" -prune -exec rm -rf {} + 2>/dev/null || true
  done
  find . -path "*/output/*" -type f \( \
      -name "base_only.mp4" -o -name "base_dyn.mp4" \
      -o -name "composite_nosfx.mp4" -o -name "composite_withsfx.mp4" \
      -o -name "_composite_pass*.mp4" -o -name "*.mov" -o -name "*.wav" \
    \) -delete 2>/dev/null || true
  df -h /app/uploads | tail -1
' || echo "[deploy] WARNING: uploads janitor skipped (backend not ready?)"

if [ -n "${BACKEND_DOMAIN:-}" ] && [ "$BACKEND_DOMAIN" != "localhost" ]; then
  echo "[deploy] Checking public HTTPS endpoint (info only)..."
  if curl -fsS --max-time 15 "https://${BACKEND_DOMAIN}/api/health" >/tmp/autoedit-public-health.json 2>/dev/null; then
    echo "[deploy] Public HTTPS health OK: https://${BACKEND_DOMAIN}/api/health"
  else
    # Depuis le VPS lui-même, joindre son propre domaine public peut échouer
    # (hairpin NAT) MÊME quand le site est parfaitement accessible de l'extérieur.
    # C'est purement informatif: la santé applicative réelle est validée
    # ci-dessus sur le conteneur backend.
    echo "[deploy] INFO: auto-test HTTPS interne non concluant (hairpin NAT possible)."
    echo "         Vérifie depuis l'extérieur: curl https://${BACKEND_DOMAIN}/api/health"
  fi
fi

echo "[deploy] Done. Set Netlify VITE_API_URL to: https://${BACKEND_DOMAIN:-YOUR_BACKEND_DOMAIN}/api"
