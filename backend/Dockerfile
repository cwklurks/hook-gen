# Backend API Dockerfile
# Deploy to Render.com or any Docker-compatible platform
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for audio processing
# ffmpeg is required for decoding MP3, M4A, and other compressed formats
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy shared package first (now accessible from root context)
COPY packages/hookgen_core /packages/hookgen_core

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
