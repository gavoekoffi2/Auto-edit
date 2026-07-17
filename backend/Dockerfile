FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# Dependances systeme (FFmpeg, ImageMagick, libs pour OpenCV/PySceneDetect,
# polices pour les overlays PIL + les sous-titres ASS/libass du moteur Auto Edit)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    libsm6 \
    libxext6 \
    libmagic1 \
    git \
    curl \
    tini \
    fontconfig \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    nodejs \
    npm \
    chromium \
    && rm -rf /var/lib/apt/lists/* \
    && (sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml 2>/dev/null || true)
# NB: le `|| true` est PARENTHÉSÉ pour ne couvrir QUE le sed ImageMagick.
# Avant, il s'appliquait à toute la chaîne: un échec d'apt-get (réseau…)
# produisait une image "réussie" SANS ffmpeg/fontconfig — panne silencieuse.
RUN command -v ffmpeg >/dev/null && command -v fc-cache >/dev/null

# Les polices d'affichage (Anton/Bangers/Bebas/Montserrat/Poppins/Caveat,
# toutes sous licence OFL) sont EMBARQUÉES dans le repo
# (app/autoedit_engine/assets/fonts) : le build est reproductible et ne
# dépend d'aucun téléchargement externe. Elles sont installées dans
# fontconfig après le COPY du code (voir plus bas).

# User non-root (UID/GID 1000 — match l'host pour eviter les soucis de volume)
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --create-home --home-dir /home/app app

COPY requirements.txt .
# Force CPU-only PyTorch before installing openai-whisper. Without this,
# recent torch wheels pull multi-GB CUDA dependencies and can fill small VPS disks.
# openai-whisper declares a Triton dependency that is only useful for GPU kernels;
# install it with --no-deps after all CPU/runtime deps to keep VPS images small.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.7.1 \
    && grep -v '^openai-whisper==' requirements.txt > /tmp/requirements-no-whisper.txt \
    && pip install --no-cache-dir -r /tmp/requirements-no-whisper.txt \
    && pip install --no-cache-dir tiktoken numba more-itertools \
    && pip install --no-cache-dir --no-deps openai-whisper==20250625 \
    && rm -f /tmp/requirements-no-whisper.txt

COPY . .

# HyperFrames is selected in production (VIDEO_RENDERER=hyperframes).  Keep the
# templates and the browser runtime in the SAME backend image used by both the
# API and Celery worker; otherwise overlays silently fall back to no clip.
RUN cd /app/templates/hyperframes \
    && npm ci --omit=dev --no-audit --no-fund \
    && command -v node >/dev/null \
    && command -v chromium >/dev/null
ENV HYPERFRAMES_TEMPLATE_DIR=/app/templates/hyperframes \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# Installe les polices embarquées pour libass/fontconfig (sous-titres ASS).
RUN mkdir -p /usr/local/share/fonts/autoedit \
    && cp app/autoedit_engine/assets/fonts/*.ttf /usr/local/share/fonts/autoedit/ \
    && fc-cache -f /usr/local/share/fonts

# Volumes attendus + cache runtime non monte sous /app.
# docker-compose bind-mount ./backend:/app in dev/prod-like runs, so anything
# created under /app at image build time can be hidden by the host mount and
# become non-writable for the non-root app user.
RUN mkdir -p /app/uploads /home/app/.cache \
    && chown -R app:app /app /home/app

# Pre-cache du modele Whisper "base" pour eviter le download au 1er job.
# Geree par une variable d'env pour permettre de skip en local si besoin.
ARG PREDOWNLOAD_WHISPER=small
ENV XDG_CACHE_HOME=/home/app/.cache
RUN if [ -n "$PREDOWNLOAD_WHISPER" ] && [ "$PREDOWNLOAD_WHISPER" != "skip" ]; then \
        python -c "import whisper; whisper.load_model('$PREDOWNLOAD_WHISPER')" \
        && chown -R app:app /home/app/.cache; \
    fi

USER app

COPY --chown=app:app entrypoint.sh /entrypoint.sh
# (chmod via COPY n'est pas possible sans BuildKit, donc on prend les droits 755 du fichier source)

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
