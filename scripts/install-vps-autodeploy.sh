#!/usr/bin/env bash
# =============================================================================
#  Installe le déploiement automatique PULL-BASED sur le VPS (à lancer UNE fois).
#
#  Après ça, chaque push sur `main` est déployé tout seul en ~2 min, sans que
#  GitHub ait besoin de joindre le serveur (le VPS interroge GitHub lui-même).
#
#  Usage (en root sur le VPS, depuis le dossier du projet):
#     sudo APP_DIR=/opt/Auto-edit BACKEND_DOMAIN=autoedit.srv1305401.hstgr.cloud \
#          TLS_EMAIL=toi@exemple.com ./scripts/install-vps-autodeploy.sh
#
#  Utilise un timer systemd si disponible, sinon retombe sur cron.
# =============================================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/Auto-edit}"
INTERVAL_MIN="${INTERVAL_MIN:-2}"
SCRIPT="$APP_DIR/scripts/vps-autodeploy.sh"

if [ ! -f "$SCRIPT" ]; then
  echo "ERREUR: $SCRIPT introuvable. Lance ce script depuis le dépôt cloné dans $APP_DIR." >&2
  exit 1
fi
chmod +x "$SCRIPT" "$APP_DIR/deploy.sh" 2>/dev/null || true
touch /var/log/cutforge-autodeploy.log 2>/dev/null || true

# Variables d'env persistées pour deploy.sh (BACKEND_DOMAIN / TLS_EMAIL).
ENV_LINE=""
[ -n "${BACKEND_DOMAIN:-}" ] && ENV_LINE="BACKEND_DOMAIN=${BACKEND_DOMAIN} "
[ -n "${TLS_EMAIL:-}" ] && ENV_LINE="${ENV_LINE}TLS_EMAIL=${TLS_EMAIL} "

if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  echo "[install] systemd détecté — création du service + timer ($INTERVAL_MIN min)…"
  cat >/etc/systemd/system/cutforge-autodeploy.service <<EOF
[Unit]
Description=CutForge pull-based auto-deploy
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
Environment=APP_DIR=$APP_DIR ${ENV_LINE}
ExecStart=/usr/bin/env bash $SCRIPT
EOF

  cat >/etc/systemd/system/cutforge-autodeploy.timer <<EOF
[Unit]
Description=Run CutForge auto-deploy every $INTERVAL_MIN min

[Timer]
OnBootSec=1min
OnUnitActiveSec=${INTERVAL_MIN}min
AccuracySec=15s
Persistent=true

[Install]
WantedBy=timers.target
EOF

  systemctl daemon-reload
  systemctl enable --now cutforge-autodeploy.timer
  echo "[install] ✅ Timer actif. Statut:"
  systemctl status cutforge-autodeploy.timer --no-pager --lines=0 || true
  echo "[install] Logs:  journalctl -u cutforge-autodeploy.service -f   OU   tail -f /var/log/cutforge-autodeploy.log"
else
  echo "[install] systemd absent — installation d'une tâche cron (*/$INTERVAL_MIN min)…"
  CRON_CMD="*/$INTERVAL_MIN * * * * cd $APP_DIR && APP_DIR=$APP_DIR ${ENV_LINE}bash $SCRIPT >> /var/log/cutforge-autodeploy.log 2>&1"
  ( crontab -l 2>/dev/null | grep -v 'vps-autodeploy.sh' ; echo "$CRON_CMD" ) | crontab -
  echo "[install] ✅ Cron installé:"
  crontab -l | grep vps-autodeploy.sh || true
fi

echo "[install] Premier déploiement immédiat…"
APP_DIR="$APP_DIR" ${ENV_LINE:+env $ENV_LINE} bash "$SCRIPT" --force || true
echo "[install] Terminé. Chaque push sur main se déploiera désormais tout seul."
