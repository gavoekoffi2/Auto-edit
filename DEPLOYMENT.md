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

# 3. Lancer le compose prod
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 4. Vérifier que tout démarre
docker compose ps
docker compose logs -f backend worker | head -50
curl -f http://localhost/api/health
```

Le `/api/health` doit retourner `{"status":"healthy","database":"connected","redis":"connected"}`.

---

## 5. Configurer le webhook FedaPay

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
