# AutoEdit - AI Video Editing SaaS Platform

AI-powered automatic video editing platform. Upload your video, choose a mode, and let AutoEdit handle the rest.

## Architecture

```
AutoEdit/
├── backend/          # FastAPI + Celery backend
│   ├── app/
│   │   ├── api/v1/       # REST API endpoints
│   │   ├── models/       # SQLAlchemy models
│   │   ├── processing/   # Video processing pipeline
│   │   ├── workers/      # Celery async tasks
│   │   └── services/     # Auth, storage, payments
│   └── alembic/          # Database migrations
├── frontend/         # React + Vite + Tailwind
│   └── src/
│       ├── pages/        # Landing, Login, Dashboard, Editor, Pricing
│       ├── components/   # Reusable UI components
│       ├── api/          # API client
│       └── store/        # Zustand state management
├── nginx/            # Reverse proxy config
└── docker-compose.yml
```

## Tech Stack

**Backend:**
- FastAPI (async Python web framework)
- PostgreSQL + SQLAlchemy (database)
- Celery + Redis (async job queue)
- OpenAI Whisper (AI transcription)
- auto-editor (silence removal)
- PySceneDetect (scene detection)
- MoviePy (video effects & compositing)

**Frontend:**
- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- Zustand (state management)
- React Router v6 (routing)

**Infrastructure:**
- Docker + Docker Compose
- Nginx (reverse proxy)
- FedaPay (payments / Mobile Money)

## Processing Pipeline

Deux pipelines coexistent — opt-in via `pipeline_version` sur le job:

**V1 (stable, par défaut):**
```
Upload → Whisper → auto-editor (silences) → PySceneDetect → MoviePy effects → Subtitles → Export
```

**V2 (IA Afrique francophone — voir [docs/VIDEO_PIPELINE_ARCHITECTURE.md](docs/VIDEO_PIPELINE_ARCHITECTURE.md)):**
```
Upload → Whisper (word-level) → Silence detect → EDL (filler words FR/EN)
       → BrollPlanner (Afrique) → OpenRouter image gen → Ken Burns FFmpeg
       → Overlays (intro/CTA) → FFmpeg final render (9:16 + captions + music)
```

### Editing Modes (V2)

| Mode | Description |
|------|-------------|
| **TikTok viral** | 9:16 + captions animées + B-roll IA + CTA |
| **Business premium 🇸🇳🇨🇮🇹🇬** | Style africain moderne + musique sobre |
| **Publicité locale** | Restaurant / boutique / service local + CTA clair |
| **Podcast propre** | Suppression silences uniquement |
| **Formation / éducatif** | Captions lisibles + B-roll discret + horizontal |

Les modes V1 historiques (`tiktok`, `youtube`, `podcast`) restent supportés.

### Audit & architecture

- [`AUTOEDIT_AUDIT.md`](AUTOEDIT_AUDIT.md) — audit technique complet, bugs corrigés, manques.
- [`docs/VIDEO_PIPELINE_ARCHITECTURE.md`](docs/VIDEO_PIPELINE_ARCHITECTURE.md) — pipeline V2, contrats, EDL, intégration HyperFrames / Remotion / video-use / OpenRouter.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/gavoekoffi2/auto-edit.git
cd auto-edit

# Copy environment variables
cp .env.example .env

# Start all services
docker-compose up --build
```

### Access
- **Frontend:** http://localhost (or http://localhost:3000)
- **API:** http://localhost/api/v1
- **API Docs:** http://localhost:8000/docs

### Development (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/auth/signup` | No | Create account |
| POST | `/api/v1/auth/login` | No | Login |
| POST | `/api/v1/auth/refresh` | No | Refresh token |
| GET | `/api/v1/auth/me` | Yes | Get profile |
| POST | `/api/v1/videos/upload` | Yes | Upload video |
| GET | `/api/v1/videos` | Yes | List videos |
| GET | `/api/v1/videos/{id}` | Yes | Get video |
| GET | `/api/v1/videos/{id}/stream` | Yes | Stream video |
| DELETE | `/api/v1/videos/{id}` | Yes | Delete video |
| POST | `/api/v1/jobs` | Yes | Create processing job |
| GET | `/api/v1/jobs/modes` | No | Catalogue des modes (v1 + v2) + defaults |
| GET | `/api/v1/jobs/{id}` | Yes | Get job status |
| POST | `/api/v1/jobs/{id}/cancel` | Yes | Cancel job |
| GET | `/api/v1/jobs/{id}/download` | Yes | Download result |
| POST | `/api/v1/payments/checkout` | Yes | Create checkout |
| POST | `/api/v1/payments/webhook` | No | FedaPay webhook |
| GET | `/api/v1/payments/plans` | No | Get pricing plans |

## Pricing

| Plan | Price (XOF) | Price (USD) | Features |
|------|-------------|-------------|----------|
| Free | 0 | $0 | 2 videos/month, 5min max, 720p |
| Pro | 5,000 FCFA | $10 | Unlimited, 30min max, 1080p, all AI modes |
| Enterprise | 15,000 FCFA | $30 | Unlimited, no limit, 4K, API access |

## Environment Variables

Voir `.env.example` pour la liste complète. Essentielles :

- `DATABASE_URL`, `DATABASE_URL_SYNC` — PostgreSQL
- `REDIS_URL` — Redis pour Celery
- `SECRET_KEY` — JWT signing key (**obligatoire en prod**, min 32 chars)
- `FEDAPAY_SECRET_KEY`, `FEDAPAY_PUBLIC_KEY` — paiement
- `WHISPER_MODEL` — taille du modèle (`tiny`/`base`/`small`/`medium`/`large`)

Pipeline V2 (B-roll IA Afrique) :

- `PIPELINE_VERSION=v1|v2` — pipeline par défaut côté worker
- `OPENROUTER_API_KEY` — clé API OpenRouter (**jamais en clair dans le repo**)
- `IMAGE_GENERATION_PROVIDER=openrouter` / `IMAGE_GENERATION_MODEL=google/gemini-2.5-flash-image-preview`
- `BROLL_STYLE=african_business_premium`
- `VIDEO_RENDERER=ffmpeg|hyperframes|remotion`
- `ENABLE_AI_BROLL`, `ENABLE_DYNAMIC_CAPTIONS`, `ENABLE_MUSIC`, `ENABLE_SFX`

## Tests & smoke check

```bash
cd backend
python -m pytest tests/ -q              # 8 tests (EDL, broll planner, providers)
python scripts/smoke_pipeline_v2.py     # smoke import + planner end-to-end
```

## License

MIT
