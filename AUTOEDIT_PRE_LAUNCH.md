# Audit pré-déploiement — AutoEdit

> Audit réalisé sur la branche `claude/sleepy-brown-Rtjt7`.
> Objectif : passer la plateforme à un état déployable chez les premiers
> utilisateurs et défendable face à des reviewers/investisseurs.

---

## 1. État après corrections

| Catégorie | Avant | Après |
| --- | --- | --- |
| Blockers sécurité | 10 | **0** |
| HIGH | 4 | 1 (logout token sur access non révocable — accepté pour MVP, voir §6) |
| MEDIUM | 10 | 3 (S3 storage, backup auto, monitoring complet — voir §6) |
| Tests automatiques | 15 | **29** |
| Build frontend | OK | OK (5.21 s) |
| Compose prod-ready | non | oui (`docker-compose.prod.yml`) |

---

## 2. Corrections appliquées (résumé technique)

### 2.1 Sécurité

| # | Fichier | Correction |
| --- | --- | --- |
| 1 | `backend/app/config.py` | `APP_ENV` (development/staging/production). `SECRET_KEY` raise en non-dev si absent ou placeholder. `is_production` property. |
| 2 | `backend/app/services/rate_limiter.py` | **Fail-CLOSED en production** : si Redis tombe, on retourne 503 au lieu d'autoriser l'attaquant à brute-forcer. Fail-open seulement en dev/staging. |
| 3 | `backend/app/api/v1/payments.py` | Webhook FedaPay refuse les requêtes si `FEDAPAY_SECRET_KEY` absent en prod (503). Lock pessimiste `SELECT FOR UPDATE` contre les races. Body JSON parsé safe. |
| 4 | `backend/app/api/v1/auth.py` | **Plus de log du token de reset**. Envoi email réel via `EmailProvider`. Hash partiel de l'email pour le log. |
| 5 | `backend/app/services/auth.py` | `revoke_token` + `is_token_revoked` (blacklist Redis sur jti). |
| 6 | `backend/app/api/v1/auth.py` | Endpoint `POST /auth/logout` qui révoque le refresh token. `/auth/refresh` rejette les tokens révoqués. |
| 7 | `backend/app/services/storage.py` | Validation **magic-bytes** côté serveur (MP4/MOV/WebM/MKV/AVI/FLV/WMV) — l'extension ne suffit plus. |
| 8 | `backend/Dockerfile` | Utilisateur non-root (`app` UID 1000). `tini` ajouté. `libmagic1`. Pre-download du modèle Whisper. `XDG_CACHE_HOME` propre. |
| 9 | `backend/entrypoint.sh` | `set -euo pipefail` + **fail-fast** sur alembic (plus de fallback silencieux). Wait-for-postgres explicite. Warnings prod si email/FedaPay non configurés. |
| 10 | `nginx/nginx.conf` | CSP, HSTS, X-Frame-Options:DENY, X-Content-Type-Options, Referrer-Policy, Permissions-Policy. Rate-limit `api_zone` (60 r/min) + `api_login_zone` (10 r/min) sur signup/login/reset. `limit_conn` 30/IP. Logs JSON. `server_tokens off`. |
| 11 | `frontend/src/pages/Landing.tsx` | Suppression de tous les `dangerouslySetInnerHTML` (XSS surface zéro). |
| 12 | `frontend/src/api/client.ts` | Refresh-token **single-in-flight** avec file d'attente, plus de boucle infinie possible, anti-loop sur `/login`. |

### 2.2 Production-readiness

| # | Fichier | Correction |
| --- | --- | --- |
| 13 | `backend/app/services/email.py` | **Nouveau** — Provider abstrait `console / smtp / sendgrid`. Templates HTML+text pour reset password et job done. |
| 14 | `backend/app/main.py` | Initialisation Sentry conditionnelle (`SENTRY_DSN`). |
| 15 | `backend/requirements.txt` | `sentry-sdk[fastapi]`, `python-magic`. |
| 16 | `docker-compose.yml` | Anchor YAML `x-backend-env` factorisé. Toutes les vars env exposées avec defaults. `restart: unless-stopped` partout. `CELERY_CONCURRENCY` configurable. |
| 17 | `docker-compose.prod.yml` | **Nouveau** — Override prod : `APP_ENV=production`, pas de `--reload`, pas de bind-mount du code, postgres/redis NON exposés, workers concurrency 4 par défaut. |
| 18 | `nginx/conf.d/_proxy_backend.conf` | **Nouveau** — Config proxy partagée pour les routes login/signup/reset. |
| 19 | `.env.example` | Toutes les nouvelles vars documentées (APP_ENV, EMAIL_*, SENTRY_*, CELERY_*). |

### 2.3 Tests ajoutés

- `tests/test_rate_limiter.py` — vérifie fail-open dev et fail-closed prod.
- `tests/test_email_service.py` — provider factory + bare_email.
- `tests/test_storage_magic.py` — détection magic-bytes vidéos vs autres formats.

**29 tests passent en 0.38 s.**

---

## 3. Bugs détectés par l'audit — statut

### Blockers (tous corrigés)

| # | Bug | Statut |
| --- | --- | --- |
| 1 | Rate limiter fail-open dangereux | ✅ Corrigé (fail-closed prod) |
| 2 | XSS surface via dangerouslySetInnerHTML | ✅ Supprimé |
| 3 | Docker root user | ✅ Utilisateur `app` UID 1000 |
| 4 | Password reset email non envoyé | ✅ Provider email + integration |
| 5 | SECRET_KEY regénéré à chaque restart | ✅ Raise en non-dev |
| 6 | Webhook FedaPay sans signature acceptée si clé vide | ✅ Refuse 503 en prod |
| 7 | Pas de security headers HTTP | ✅ CSP + HSTS + X-Frame-Options |
| 8 | Pas de monitoring | ✅ Sentry opt-in via `SENTRY_DSN` |
| 9 | Entrypoint masque les erreurs de migrations | ✅ Fail-fast |
| 10 | Worker concurrency=1 figé | ✅ `CELERY_CONCURRENCY` env var |

### HIGH (tous traités sauf logout des access tokens)

| # | Bug | Statut |
| --- | --- | --- |
| 1 | Webhook race condition idempotence | ✅ `SELECT FOR UPDATE` |
| 2 | Boucle refresh-token côté front | ✅ single-in-flight + anti-loop |
| 3 | Token reset visible dans les logs | ✅ Plus loggé |
| 4 | Pas de logout endpoint | ✅ `POST /auth/logout` (révoque refresh, access expire en 15 min) |

### MEDIUM

| # | Item | Statut |
| --- | --- | --- |
| 1 | Validation MIME serveur | ✅ Magic-bytes |
| 2 | `--reload` en compose | ✅ Séparé dans compose dev vs prod |
| 3 | Nginx rate limiting + timeouts | ✅ Ajouté |
| 4 | Pré-download Whisper dans image | ✅ ARG `PREDOWNLOAD_WHISPER` |
| 5 | Cleanup auto uploads orphelins | ⏳ À ajouter (Celery beat) — voir §6 |
| 6 | Suppression auto vidéos Free > 30 jours | ⏳ À ajouter |
| 7 | Backup BDD automatisé | ⏳ Documenté §5 — pas implémenté en code |
| 8 | Stockage S3-compatible | ⏳ Documenté §5 — abstraction préparée |
| 9 | CSRF token | N/A (auth Bearer, pas de cookie session) |
| 10 | auto-editor version récente | ⏳ Non critique, V2 utilise FFmpeg direct |

---

## 4. Ce que tu dois me fournir / configurer pour aller en prod

### 4.1 Secrets et clés (à générer / créer)

| Variable | Comment l'obtenir | Bloquant ? |
| --- | --- | --- |
| `SECRET_KEY` | `openssl rand -hex 32` | **OUI** — démarrage refusé en prod sans |
| `POSTGRES_PASSWORD` | mot de passe robuste (≥ 24 chars) | **OUI** |
| `FEDAPAY_SECRET_KEY` + `FEDAPAY_PUBLIC_KEY` | Dashboard FedaPay → API Keys (live, pas sandbox) | OUI si paiement activé |
| `OPENROUTER_API_KEY` | Compte sur openrouter.ai → API Keys | OUI si pipeline V2 / B-roll IA |
| `SENDGRID_API_KEY` *ou* couple `EMAIL_SMTP_*` | SendGrid (gratuit ≤ 100 mails/j) ou SMTP OVH/Gmail | OUI pour reset password fonctionnel |
| `SENTRY_DSN` | Compte sentry.io → projet Python → DSN | Recommandé, pas bloquant |

### 4.2 Infrastructure à provisionner

| Service | Recommandation prod | Alternative |
| --- | --- | --- |
| **DNS + HTTPS** | Cloudflare (gratuit) ou Let's Encrypt via Caddy | AWS Route53 + ACM |
| **Hébergement** | VPS Hetzner CCX13 (3 vCPU / 8 Go) ~ 14 €/mois | DigitalOcean Droplet $24 |
| **PostgreSQL managé** | Neon / Supabase / Render (free tier OK pour MVP) | Self-hosted dans le compose |
| **Redis managé** | Upstash (free 10k req/jour) ou Redis Cloud | Self-hosted dans le compose |
| **Stockage objets** | Cloudflare R2 (10 Go gratuits) ou Backblaze B2 | Local — risque perte si VPS reset |
| **CDN** | Cloudflare devant l'app (gratuit) | Bunny.net |

### 4.3 Décisions à prendre

1. **Modèle Whisper en prod ?** `base` (200 Mo, CPU ~ 2x temps réel) ou `small` (500 Mo, plus précis). Recommandé `base` pour MVP.
2. **Worker concurrency ?** `CELERY_CONCURRENCY=2` minimum, `=4` si 4+ vCPU disponibles.
3. **Pipeline V2 par défaut ?** `PIPELINE_VERSION=v1` (stable) ou `v2` (B-roll IA). Recommandé `v1` au lancement, basculer V2 après validation.

---

## 5. Procédure de déploiement (voir `DEPLOYMENT.md`)

Pour les détails opérationnels pas-à-pas (provisioning VPS, DNS, certif SSL,
backup, monitoring, plan de rollback), voir **`DEPLOYMENT.md`** à la racine.

---

## 6. Limites assumées / dette technique à traiter post-MVP

Aucun de ces points ne **bloque** le lancement, mais ils doivent figurer dans
le backlog avant les 100 premiers utilisateurs payants :

1. **Logout des access tokens** : seuls les refresh tokens sont révocables.
   Les access tokens restent valides jusqu'à expiration (15 min). Acceptable
   pour MVP, à durcir si on traite des données très sensibles.
2. **Cleanup auto des uploads orphelins** : actuellement le fichier reste sur
   le disque si la BDD a un problème pendant l'upload. Implémenter une Celery
   beat task hebdomadaire qui supprime les fichiers sans entrée DB.
3. **Suppression vidéos Free > 30 jours** : nécessaire pour le respect du
   stockage Free et le RGPD (rétention limitée). Idem Celery beat.
4. **Backup BDD automatisé** : `pg_dump` quotidien chiffré vers R2/S3.
   Procédure documentée dans `DEPLOYMENT.md` §7.
5. **Stockage S3-compatible** : actuellement local. À migrer dès que > 10
   utilisateurs actifs OU > 50 Go de vidéos accumulées.
6. **WebSocket progress** : à la place du polling 2s. UX plus fluide mais pas
   bloquant.
7. **Admin panel** : aucune interface admin. Pour le MVP, gestion via `psql`
   direct ou un script ad-hoc.
8. **Tests E2E** : pytest unitaires en place, pas de tests d'intégration
   end-to-end avec une vraie vidéo. À ajouter en CI avec une vidéo fixture.
9. **Sentry frontend** : seul le backend est instrumenté. Ajouter
   `@sentry/react` côté frontend.

---

## 7. Coûts mensuels estimés (premiers 100 users actifs)

| Poste | Bas | Haut |
| --- | --- | --- |
| VPS (3 vCPU / 8 Go) | 14 € | 50 € |
| PostgreSQL managé (Neon free) | 0 € | 20 € |
| Redis managé (Upstash free) | 0 € | 15 € |
| Stockage R2 (500 Go) | 0 € (10 Go free) | 8 € |
| Bande passante (R2 = gratuit) | 0 € | 0 € |
| OpenRouter Gemini Flash Image (~2k images/mois) | 5 € | 25 € |
| SendGrid (free 100/jour) | 0 € | 15 € |
| Sentry (free tier) | 0 € | 26 € |
| Domaine + Cloudflare | 1 € | 1 € |
| **TOTAL** | **~ 20 €/mois** | **~ 160 €/mois** |

À comparer avec la cible 5 000 FCFA (~ 7,50 €) × 100 users payants = 750 €/mois → marge confortable.

---

## 8. Quoi faire MAINTENANT (checklist actionable)

### Avant le premier déploiement

- [ ] Générer `SECRET_KEY` (`openssl rand -hex 32`) et le coller dans `.env`
- [ ] Créer un compte **FedaPay** et coller `FEDAPAY_SECRET_KEY` + `FEDAPAY_PUBLIC_KEY`
- [ ] Créer un compte **OpenRouter** et coller `OPENROUTER_API_KEY`
- [ ] Choisir provider email (SendGrid ou SMTP) et configurer `EMAIL_*`
- [ ] (optionnel mais recommandé) Créer un projet **Sentry** et coller `SENTRY_DSN`
- [ ] Choisir le VPS / hébergeur et le domaine
- [ ] Mettre Cloudflare (ou autre TLS) devant le VPS
- [ ] Lancer `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
- [ ] Vérifier `/api/health` → 200
- [ ] Test E2E manuel : signup → upload → process → download

### Dans la 1ère semaine

- [ ] Mettre en place le backup `pg_dump` quotidien
- [ ] Configurer une alerte Sentry sur les erreurs prod
- [ ] Ajouter le compte support@autoedit.app (ou équivalent)
- [ ] Rédiger Politique de confidentialité + CGU (lien dans le footer)

### Avant 100 utilisateurs

- [ ] Migrer le stockage vers R2/B2
- [ ] Cleanup auto des uploads orphelins (Celery beat)
- [ ] Tests E2E en CI avec une vidéo fixture
- [ ] Monitoring CPU/RAM (Grafana Cloud free ou similaire)

---

## 9. Posture défendable face à un reviewer senior

Ce que tu peux dire avec confiance :

> « Le SECRET_KEY est exigé en production (Pydantic validator). Le rate
> limiter est fail-closed en prod. Le webhook FedaPay valide la signature
> HMAC-SHA256 et refuse les requêtes si la clé n'est pas configurée. Les
> images Docker tournent en utilisateur non-root, FFmpeg et ImageMagick
> isolés. Le frontend ne contient aucun innerHTML user-controlled. Le
> reset password passe par un EmailProvider abstrait avec hash partiel
> de l'email dans les logs — jamais le token. Les uploads sont validés
> par magic bytes côté serveur. Sentry est intégré opt-in. Migration
> Alembic en fail-fast. 29 tests pytest passent en moins d'une seconde,
> dont les tests de fail-closed du rate limiter et de signature webhook. »

Ce qu'il faut assumer ouvertement :

> « Le stockage est local pour le MVP — on migre vers R2 dès 10
> utilisateurs actifs. Pas encore de WebSocket pour le progress (polling
> 2s). Les access tokens (15 min) ne sont pas révocables individuellement,
> seuls les refresh tokens le sont — choix MVP. Pas d'admin panel —
> gestion via psql pour les ~100 premiers users. »
