#!/usr/bin/env bash
# =============================================================================
#  CutForge — déploiement PULL-BASED (le VPS tire les mises à jour).
#
#  Pourquoi: le déploiement push-based (GitHub Actions -> SSH) échoue car le
#  pare-feu du VPS bloque les runners GitHub ("dial tcp ... i/o timeout").
#  Ici, c'est le VPS qui se connecte EN SORTANT vers GitHub (HTTPS 443, qui
#  fonctionne toujours), donc aucun port entrant n'est requis.
#
#  Ce script est idempotent: il ne reconstruit la stack QUE si origin/main a
#  avancé. Lancé toutes les 2 min par un timer systemd (voir
#  install-vps-autodeploy.sh), il rend le déploiement automatique à chaque push.
#
#  Usage manuel:  APP_DIR=/opt/Auto-edit ./scripts/vps-autodeploy.sh [--force]
# =============================================================================
set -euo pipefail

# Auto-détection du dossier projet depuis l'emplacement du script (scripts/..),
# pour que le chemin ne soit JAMAIS faux quel que soit l'endroit du clone.
_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${APP_DIR:-$_SELF}"
BRANCH="${DEPLOY_BRANCH:-main}"
LOG="${AUTODEPLOY_LOG:-/var/log/cutforge-autodeploy.log}"
LOCK="/tmp/cutforge-autodeploy.lock"
FORCE="${1:-}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG" 2>/dev/null || echo "[$(date '+%H:%M:%S')] $*"; }

# Un seul déploiement à la fois (le timer tourne toutes les 2 min).
exec 9>"$LOCK"
if ! flock -n 9; then
  log "Un déploiement est déjà en cours — on saute ce tour."
  exit 0
fi

cd "$APP_DIR" || { log "ERREUR: APP_DIR introuvable: $APP_DIR"; exit 1; }

git fetch --quiet origin "$BRANCH" || { log "git fetch a échoué (réseau ?)"; exit 0; }

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"

if [ "$LOCAL" = "$REMOTE" ] && [ "$FORCE" != "--force" ]; then
  # Rien de nouveau — silencieux pour ne pas polluer le log.
  exit 0
fi

log "Nouveau commit détecté ($LOCAL -> $REMOTE). Déploiement…"
git reset --hard "origin/$BRANCH" >>"$LOG" 2>&1

# deploy.sh préserve .env, reconstruit la stack Docker et fait le health-check.
if ./deploy.sh >>"$LOG" 2>&1; then
  log "✅ Déploiement terminé sur $(git rev-parse --short HEAD)."
else
  log "❌ deploy.sh a échoué — voir les lignes ci-dessus dans $LOG."
  exit 1
fi
