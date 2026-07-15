# Déploiement AutoEdit

> Procédure opérationnelle pour amener AutoEdit en production chez les
> premiers utilisateurs. Hypothèse : un VPS Linux (Ubuntu 22.04+) avec
> Docker installé, un domaine, et un accès SSH root.

---

## 1. Avant de commencer — checklist matériel & comptes

| Élément | Obligatoire | Pourquoi |
| --- | --- | --- |
| Domaine (ex. `autoedit.app`) | oui | Pour HTTPS + CORS |
| VPS ≥ 3 vCPU / 8 Go RAM / 80 Go disque | oui | Whisper + FFmpeg gourmands |
| Compte Cloudflare (gratuit) | recommandé | HTTPS + DDoS + CDN |
| Compte FedaPay | oui (si paiement) | Mobile Money + carte |
| Compte OpenRouter | oui (si pipeline V2) | Génération images B-roll |
| Compte SendGrid (ou SMTP) | oui | Reset password fonctionnel |
| Compte Sentry | recommandé | Visibilité erreurs prod |

---

## 2. Préparer les secrets

### 2.1 Générer SECRET_KEY

```bash
openssl rand -hex 32
# colle la sortie dans SECRET_KEY=
```

### 2.2 Récupérer les clés tierces

- **FedaPay** : Dashboard → Paramètres → Clés API → mode **Live** (pas sandbox).
  Récupère `secret_key` et `public_key`.
- **OpenRouter** : openrouter.ai → Settings → Keys → "Create Key".
- **SendGrid** : Settings → API Keys → "Restricted Access" (Mail Send only).
- **Sentry** : Projects → AutoEdit → Settings → Client Keys (DSN).

### 2.3 Construire le `.env`

Sur le VPS, copier `.env.example` en `.env` et remplir TOUS les `*_KEY` /
`*_PASSWORD`, plus :

```env
APP_ENV=production
PUBLIC_APP_URL=https://autoedit.app
CORS_ORIGINS=https://autoedit.app
EMAIL_PROVIDER=sendgrid      # ou smtp
PIPELINE_VERSION=v1          # v2 quand on aura validé en prod
CELERY_CONCURRENCY=4         # adapter au nombre de vCPU
POSTGRES_PASSWORD=...        # mot de passe robuste (≥ 24 chars)
```

⚠️ **Ne committe JAMAIS ce fichier.** Il est dans `.gitignore` mais
vérifie avant chaque push.

---

## 3. Mettre en place HTTPS

### Option A — Cloudflare (recommandé, le plus simple)

1. Ajoute le domaine sur Cloudflare, change les NS chez ton registrar.
2. DNS A record `@` → IP du VPS (proxied ☁️).
3. SSL/TLS → mode **Full**.
4. Rules → Always Use HTTPS = on.
5. Edge Certificates → HSTS = on (max-age 6 mois).

C'est tout. Le nginx interne reste en HTTP 80, Cloudflare terminate le TLS.

### Option B — Caddy en reverse-proxy (sans Cloudflare)

Voir `docs/deploy-with-caddy.md` (à créer si besoin).

---

## 4. Premier déploiement

```bash
# 1. Cloner le repo sur le VPS
git clone https://github.com/gavoekoffi2/Auto-edit.git
cd Auto-edit
git checkout claude/sleepy-brown-Rtjt7

# 2. Configurer .env (cf. section 2.3)
cp .env.example .env
nano .env   # remplir TOUS les secrets

# 3. Lancer le script de déploiement prod (Docker + Caddy HTTPS automatique)
BACKEND_DOMAIN=srv1305401.hstgr.cloud TLS_EMAIL=admin@example.com ./deploy.sh

# 4. Vérifier que tout démarre
curl -f https://srv1305401.hstgr.cloud/api/health
```

Le `/api/health` doit retourner `{"status":"healthy","database":"connected","redis":"connected"}`.

---

## 5. Netlify frontend

Dans Netlify → Site settings → Environment variables :

```env
VITE_API_URL=https://srv1305401.hstgr.cloud/api
```

⚠️ Il faut inclure `/api`, car le frontend ajoute ensuite `/v1` automatiquement.
Après modification : **Trigger deploy / Redeploy site**. Ajoute aussi l'URL Netlify dans `CORS_ORIGINS` côté VPS.

---

## 5bis. CI/CD — Déploiement automatique (GitHub Actions)

À chaque `git push` sur **`main`**, le déploiement se fait tout seul :

| Cible | Workflow | Déclencheur | Secrets requis |
| --- | --- | --- | --- |
| **Frontend** (Netlify) | `.github/workflows/netlify-frontend.yml` | push sur `main` | `NETLIFY_AUTH_TOKEN`, `NETLIFY_SITE_ID` |
| **Backend** (VPS) | `.github/workflows/deploy-backend.yml` | push sur `main` touchant `backend/`, `renderers/`, `templates/`, `docker-compose*.yml`, `deploy.sh`, `Caddyfile`, `nginx/` | `VPS_SSH_HOST`, `VPS_SSH_USER`, `VPS_SSH_KEY` (+ option `VPS_SSH_PORT`) |

> ⚠️ **Le déploiement backend par SSH (push-based) échoue souvent** :
> le pare-feu Hostinger bloque les runners GitHub (`dial tcp … i/o timeout`).
> Le step SSH est donc *best-effort* (non bloquant). **Le mécanisme FIABLE est
> pull-based** : le VPS interroge GitHub lui-même et se déploie tout seul.

### ⭐ Déploiement automatique FIABLE (pull-based — recommandé)

Le VPS sort vers GitHub en HTTPS (443, toujours ouvert) au lieu d'attendre une
connexion SSH entrante (bloquée). À installer **une seule fois**, en SSH sur le
VPS depuis ta machine :

```bash
cd /opt/Auto-edit
git fetch origin main && git reset --hard origin/main      # récupère les scripts
sudo APP_DIR=/opt/Auto-edit \
     BACKEND_DOMAIN=autoedit.srv1305401.hstgr.cloud \
     TLS_EMAIL=toi@exemple.com \
     ./scripts/install-vps-autodeploy.sh
```

Ça installe un **timer systemd** (`cutforge-autodeploy`, toutes les 2 min) qui :
fetch `origin/main` → si nouveau commit → `git reset --hard` + `./deploy.sh`.
Désormais **chaque push sur `main` est déployé tout seul en ≤ 2 min**, sans
dépendre du SSH entrant.

- Logs : `tail -f /var/log/cutforge-autodeploy.log` ou `journalctl -u cutforge-autodeploy -f`
- Forcer maintenant : `sudo APP_DIR=/opt/Auto-edit ./scripts/vps-autodeploy.sh --force`

### Déploiement manuel immédiat (si besoin tout de suite)

```bash
cd /opt/Auto-edit && git fetch origin main && git reset --hard origin/main && ./deploy.sh
```

### (Optionnel) Réparer le push-based SSH

Pour que `Actions > Deploy backend to VPS` réussisse aussi, il faut que le port
SSH du VPS soit joignable par les runners GitHub (souvent bloqué) et que
`VPS_SSH_HOST` pointe sur la **bonne** IP. Renseigne les 3 secrets ci-dessous.
Tant que ce n'est pas le cas, garde le pull-based ci-dessus comme mécanisme
principal.

### Mettre en place les secrets (une seule fois)

GitHub → repo **Settings → Secrets and variables → Actions → New repository secret** :

**Frontend (Netlify)**
- `NETLIFY_AUTH_TOKEN` : Netlify → User settings → Applications → *New access token*.
- `NETLIFY_SITE_ID` : Netlify → Site → Site configuration → *Site ID* (API ID).

**Backend (VPS)**
- `VPS_SSH_HOST` : ex. `srv1305401.hstgr.cloud` (ou l'IP).
- `VPS_SSH_USER` : ex. `root`.
- `VPS_SSH_KEY` : une **clé privée** dédiée au déploiement. Sur ta machine :
  ```bash
  ssh-keygen -t ed25519 -f deploy_key -N ""                     # crée deploy_key (+ .pub)
  ssh-copy-id -i deploy_key.pub root@srv1305401.hstgr.cloud      # autorise la clé sur le VPS
  # Colle le CONTENU de deploy_key (la clé PRIVÉE) dans le secret VPS_SSH_KEY
  ```
- `VPS_SSH_PORT` *(optionnel)* : si SSH n'est pas sur 22.
- Variable optionnelle `VPS_APP_DIR` (Settings → Variables) : dossier du repo sur
  le VPS, défaut `/opt/Auto-edit`.

**Prérequis VPS** : le repo doit déjà être cloné dans `VPS_APP_DIR` avec le
remote `origin` (cf. §4). Le workflow fait `git fetch && git reset --hard
origin/main` puis lance `./deploy.sh` (qui préserve le `.env`, rebuild la stack
Docker et vérifie `/api/health`).

### Le flux au quotidien

```
modif de code  ->  git push origin main  ->  Actions :
                                              • build + deploy Netlify (frontend)
                                              • ssh + deploy.sh sur le VPS (backend)
```

Déclenchement manuel aussi possible : onglet **Actions** → choisir le workflow →
*Run workflow*. Les branches de feature (`claude/*`) ne déploient **pas** le
live ; on ouvre une PR vers `main` puis on merge pour publier.

---

## 6. Configurer le webhook FedaPay

Dans le dashboard FedaPay, ajouter un webhook qui pointe vers :

```
https://autoedit.app/api/v1/payments/webhook
```

FedaPay enverra le header `X-Fedapay-Signature` — le backend vérifie le HMAC.

---

## 6. Tests post-déploiement

Test E2E manuel obligatoire avant d'ouvrir aux utilisateurs :

```
[ ] Signup avec un email réel → reçoit-on un compte créé en BDD ?
[ ] Login fonctionne
[ ] /auth/me retourne le user
[ ] Reset password : email reçu avec lien valide
[ ] Upload d'une vidéo MP4 (< 50 Mo pour test rapide)
[ ] Création d'un job mode "business_premium_african"
[ ] Polling /jobs/{id} → progress monte
[ ] Download du résultat → MP4 valide
[ ] (si V2 activé) /jobs/{id} → result.broll.successes > 0
[ ] Logout → /auth/refresh avec l'ancien token retourne 401
[ ] Tests rate-limit : 6 logins ratés en 15 min depuis la même IP → 429
[ ] Tests CORS : requête depuis un domaine non whitelisté → bloquée
```

---

## 7. Backup PostgreSQL (à automatiser)

### 7.1 Script `backup.sh` (à placer dans `/opt/autoedit/backup.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail
TS=$(date +%Y%m%d-%H%M%S)
DEST=/var/backups/autoedit
mkdir -p "$DEST"
docker compose exec -T postgres pg_dump -U autoedit autoedit | gzip > "$DEST/autoedit-$TS.sql.gz"
# Garde 14 jours
find "$DEST" -name 'autoedit-*.sql.gz' -mtime +14 -delete
# Upload optionnel vers R2/B2 :
# rclone copy "$DEST/autoedit-$TS.sql.gz" r2:autoedit-backups/
```

### 7.2 Cron quotidien

```cron
0 3 * * * /opt/autoedit/backup.sh >> /var/log/autoedit-backup.log 2>&1
```

### 7.3 Test de restore (faire 1x au moins)

```bash
docker compose exec -T postgres psql -U autoedit -c "DROP DATABASE autoedit_test;"
docker compose exec -T postgres psql -U autoedit -c "CREATE DATABASE autoedit_test;"
gunzip -c /var/backups/autoedit/autoedit-LATEST.sql.gz | \
  docker compose exec -T postgres psql -U autoedit autoedit_test
```

---

## 8. Monitoring

### 8.1 Sentry (déjà intégré)

Si `SENTRY_DSN` est dans `.env`, le backend remonte automatiquement les
exceptions. Ajoute dans Sentry une alerte sur `error.count > 5 / 5min`.

### 8.2 Uptime externe

UptimeRobot (gratuit) → check `https://autoedit.app/api/health` toutes les
5 min. Alerte SMS/email si down.

### 8.3 Logs

```bash
# Logs backend en streaming
docker compose logs -f --tail=200 backend worker

# Recherche d'erreurs
docker compose logs backend | grep -i "ERROR\|exception"
```

---

## 9. Procédures opérationnelles

### 9.1 Déployer une nouvelle version

```bash
cd /opt/autoedit
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
# Vérifier la santé
sleep 10
curl -f https://autoedit.app/api/health
```

### 9.2 Rollback

```bash
git log --oneline -10                # repérer le commit avant le bug
git checkout <SHA_PRECEDENT>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 9.3 Redémarrage propre

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend worker
```

### 9.4 Si Redis tombe

Le rate limiter passe en fail-closed → l'auth renvoie 503. Redémarre Redis :

```bash
docker compose restart redis
```

### 9.5 Si Postgres tombe

Tous les endpoints qui touchent la BDD retournent 500. Restaure depuis backup :

```bash
docker compose down postgres
docker compose up -d postgres
sleep 5
gunzip -c /var/backups/autoedit/autoedit-LATEST.sql.gz | \
  docker compose exec -T postgres psql -U autoedit autoedit
```

---

## 10. Mises à jour de sécurité

À faire **tous les mois** :

```bash
# Mise à jour OS
sudo apt update && sudo apt upgrade -y

# Mise à jour des images Docker
docker compose pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Audit Python (sur le repo)
pip install pip-audit
pip-audit -r backend/requirements.txt

# Audit npm
cd frontend && npm audit --production
```

---

## 11. Avant d'ouvrir l'inscription publique

- [ ] `.env` complet et stable (test sur staging d'abord si possible)
- [ ] HTTPS forcé (test : `curl -I http://autoedit.app` → 301 vers https)
- [ ] Webhook FedaPay reçu avec succès (faire un paiement test)
- [ ] Email reset reçu sur un vrai email (Gmail, Yahoo)
- [ ] Backup pg_dump testé et restauré
- [ ] Sentry remonte une erreur de test (`raise Exception` dans un endpoint, puis retirer)
- [ ] Politique de confidentialité publiée à `/privacy`
- [ ] Conditions générales publiées à `/terms`
- [ ] Page de status / contact `support@<domain>` configurée
- [ ] Plan de rollback testé une fois
- [ ] Plan de communication "incident" prêt (template email/Slack)

Une fois ces 11 cases cochées : **ouvre l'inscription, commence par 10
utilisateurs cibles, observe pendant 48h, scale**.

---

## 12. Fonctionnalité « Clips » + moteur v4.3 — spécificités de déploiement

### 12.1 Nouvelles dépendances (image backend/worker à reconstruire)

| Dépendance | Source | Version | Rôle |
| --- | --- | --- | --- |
| `yt-dlp` | requirements.txt | `>=2025.1.15` | import de vidéos par URL. Mettre à jour régulièrement (les extracteurs de plateformes cassent avec le temps) mais TESTER avant de déployer — jamais de mise à jour automatique silencieuse. |
| `opencv-python-headless` | requirements.txt | `>=4.9,<5` (épinglé: 5.x retire l'API Haar) | recadrage vertical intelligent (suivi de visage) |
| Polices OFL (Anton, Bangers, Bebas, Montserrat, Poppins, Caveat) | **embarquées dans le repo** `backend/app/autoedit_engine/assets/fonts/` | figées par commit | sous-titres des styles. Plus aucun téléchargement réseau au build. Licence: `OFL-LICENSE.txt` dans le même dossier. |

```bash
docker compose build backend worker && docker compose up -d
# Vérifier :
docker compose exec backend python -c "import cv2, yt_dlp, whisper; print('deps ok')"
docker compose exec backend fc-list | grep -iE "poppins|caveat|anton"
```

### 12.2 Purge de rétention (celery beat)

La purge automatique des fichiers (rendus > `RETENTION_OUTPUT_DAYS`, sources
URL > `RETENTION_SOURCE_DAYS`, jobs échoués > `RETENTION_FAILED_JOB_DAYS`)
tourne via **celery beat**. Ajouter un service beat au compose :

```yaml
  beat:
    build: ./backend
    command: celery -A app.workers.celery_app beat --loglevel=info
    env_file: .env
    depends_on: [redis]
```

Sans beat, exécuter à la main / via cron :
`docker compose exec worker celery -A app.workers.celery_app call purge_expired_files`

### 12.3 Endpoints de santé

- `GET /api/health/live` — liveness (jamais de dépendance)
- `GET /api/health/ready` — readiness DB + Redis (503 si KO) → à utiliser
  dans le health-check du proxy/orchestrateur
- `GET /api/health` — état global + disque (les détails d'erreur vont dans
  les logs, pas dans la réponse publique)

### 12.4 Nouvelles variables d'environnement

Voir `.env.example` (sections « Nettoyage IA », « Fonctionnalité Clips »,
« Rétention », « Recadrage vertical ») : `ENGINE_LLM_CLEANUP*`,
`ENGINE_VIRAL_MOMENTS_MODEL`, `CLIPS_MAX_*`, `RETENTION_*`, `SMART_CROP_MODE`.
Toutes ont des valeurs par défaut saines — rien n'est obligatoire.

### 12.5 Limites documentées (MVP Clips)

- Rendu final vertical 1080x1920 uniquement (MP4/H.264/AAC — compatible
  TikTok / Reels / Shorts).
- Recadrage intelligent : un cadrage par segment d'EDL (pas de panoramique
  continu dans un segment), visage dominant par segment, pas encore de
  split-screen deux intervenants ni de diarisation. Fallback centre journalisé
  (`result.montage.smart_crop`).
- La sélection des extraits (étape 2) réutilise la transcription de l'analyse ;
  si les fichiers d'analyse ont été purgés, le rendu retranscrit la source.
- Les libellés fins de progression ne sont pas persistés en base (le
  pourcentage par étape l'est).

## 13. Checklist complémentaire — lancement Clips / premiers utilisateurs

En plus de la checklist §11 :

- [ ] Image backend/worker reconstruite (yt-dlp + OpenCV + polices) et vérifiée (§12.1)
- [ ] Service `beat` actif → purge de rétention observée dans les logs (§12.2)
- [ ] `GET /api/health/ready` branché sur le health-check du proxy
- [ ] Quotas par plan revus (`CLIPS_MAX_*`) et testés : dépassement → erreur `[QUOTA_*]` claire
- [ ] Test réel : URL YouTube publique → analyse → sélection → rendu → téléchargement
- [ ] Test réel : fichier importé depuis un téléphone (réseau mobile)
- [ ] Test négatif : URL privée, URL invalide, vidéo sans parole → messages d'erreur codifiés
- [ ] Tentative de téléchargement du clip d'un autre compte → 404 (ownership)
- [ ] Consentement « droits sur la vidéo » visible dans l'interface Clips
- [ ] PRIVACY.md reflété dans la politique de confidentialité publiée (fournisseurs IA, rétention, suppression)
- [ ] Espace disque : alerte < 10 % libre + rétention adaptée au trafic attendu
- [ ] Rotation des clés testée (OpenRouter/ElevenLabs) : §9
