FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# Dependances systeme (FFmpeg, ImageMagick, libs pour OpenCV/PySceneDetect)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    libsm6 \
    libxext6 \
    libmagic1 \
    git \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml 2>/dev/null || true

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

# Volumes attendus
RUN mkdir -p /app/uploads /app/whisper_cache \
    && chown -R app:app /app /home/app

# Pre-cache du modele Whisper "base" pour eviter le download au 1er job.
# Geree par une variable d'env pour permettre de skip en local si besoin.
ARG PREDOWNLOAD_WHISPER=base
ENV XDG_CACHE_HOME=/app/whisper_cache
RUN if [ -n "$PREDOWNLOAD_WHISPER" ] && [ "$PREDOWNLOAD_WHISPER" != "skip" ]; then \
        python -c "import whisper; whisper.load_model('$PREDOWNLOAD_WHISPER')" \
        && chown -R app:app /app/whisper_cache; \
    fi

USER app

COPY --chown=app:app entrypoint.sh /entrypoint.sh
# (chmod via COPY n'est pas possible sans BuildKit, donc on prend les droits 755 du fichier source)

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
