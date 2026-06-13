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

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
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

# Build and start all services.
echo "[deploy] Building and starting AutoEdit production stack..."
"${COMPOSE[@]}" up -d --build

echo "[deploy] Services:"
"${COMPOSE[@]}" ps

echo "[deploy] Waiting for API health..."
for i in {1..30}; do
  if curl -fsS --max-time 5 -H "Host: ${BACKEND_DOMAIN:-localhost}" http://localhost/api/health >/tmp/autoedit-health.json 2>/dev/null; then
    echo "[deploy] Local health OK: $(cat /tmp/autoedit-health.json)"
    break
  fi
  sleep 2
  if [ "$i" = "30" ]; then
    echo "[deploy] ERROR: API health did not become reachable on http://localhost/api/health" >&2
    "${COMPOSE[@]}" logs --tail=120 backend worker caddy >&2 || true
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
  echo "[deploy] Checking public HTTPS endpoint..."
  if curl -fsS --max-time 15 "https://${BACKEND_DOMAIN}/api/health" >/tmp/autoedit-public-health.json 2>/dev/null; then
    echo "[deploy] Public HTTPS health OK: https://${BACKEND_DOMAIN}/api/health"
  else
    echo "[deploy] WARNING: public HTTPS health not reachable yet. Check DNS A record, ports 80/443, and Caddy logs:"
    echo "         ${COMPOSE[*]} logs -f caddy"
  fi
fi

echo "[deploy] Done. Set Netlify VITE_API_URL to: https://${BACKEND_DOMAIN:-YOUR_BACKEND_DOMAIN}/api"
