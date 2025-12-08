# Backend API Dockerfile
# Deploy to Render.com or any Docker-compatible platform
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for audio processing
# ffmpeg is required for decoding MP3, M4A, and other compressed formats
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
