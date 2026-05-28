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
- Remotion (React-based motion design: animated intros, captions, end-screens)

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

```
Upload → Whisper AI Transcription → Silence Removal → Scene Detection →
Effects → Subtitles → Motion Design (Remotion) → Export
```

### Editing Modes

| Mode | Description |
|------|-------------|
| **TikTok** | Vertical crop (9:16), fast cuts, animated centered captions, branded intro/outro, 60s max |
| **YouTube** | Optimized engagement, silence removal, scene chapters, animated captions + intro/outro |
| **Podcast** | Audio cleanup, silence removal, full transcription |

### Motion Design (Remotion)

Animated motion graphics are added by the `remotion/` project, driven from the
Celery worker (`backend/app/processing/motion.py`):

- **Animated intro** — branded opener with word-by-word title reveal
- **Animated captions** — word-by-word transcript overlay (transparent ProRes,
  composited with ffmpeg) that auto-matches the source aspect ratio
- **End-screen / outro** — animated call-to-action (Subscribe / Follow)
- **Lower-thirds** — name/role banners

Users toggle motion design and pick a brand color / intro title per render in
the editor. The step degrades gracefully: if Node/Remotion is unavailable the
job still completes without motion graphics.

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
| GET | `/api/v1/jobs/{id}` | Yes | Get job status |
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

See `.env.example` for all configuration options:
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis for Celery
- `SECRET_KEY` - JWT signing key
- `FEDAPAY_SECRET_KEY` - Payment provider
- `WHISPER_MODEL` - Whisper model size (base, small, medium, large)

## License

MIT
