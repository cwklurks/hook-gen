# Stage 1: Build Frontend
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend + Static Files
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy example audio files
COPY hook-aid/examples ./examples

# Copy built frontend static files
COPY --from=frontend /frontend/out ./static

# Run the server
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}


