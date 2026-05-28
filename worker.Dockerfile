# Worker image: Python video pipeline + Node/Remotion motion design.
# Build context must be the repo root so both backend/ and remotion/ are visible.
FROM python:3.11-slim

WORKDIR /app

# System dependencies: ffmpeg + ImageMagick for the Python pipeline, and the
# shared libraries Remotion's headless Chromium needs to render.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    libsm6 libxext6 \
    git curl ca-certificates gnupg \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml 2>/dev/null || true

# Node.js 20 LTS (for Remotion).
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Remotion project: install JS deps and pre-fetch the headless browser so the
# first render does not have to download Chromium at runtime.
ENV REMOTION_DIR=/opt/remotion
COPY remotion /opt/remotion
RUN cd /opt/remotion \
    && npm install --no-audit --no-fund \
    && (npx remotion browser ensure || echo "browser ensure deferred to first render")

# Backend application code.
COPY backend /app
RUN mkdir -p /app/uploads

CMD ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
