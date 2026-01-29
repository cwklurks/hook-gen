import logging
import sys

import numpy as np
from api import endpoints
from api.rate_limit import limiter, rate_limit_exceeded_handler
from app.database import init_db
from fastapi import FastAPI, Request, Response
from hookgen_core import (
    detect_scale_from_audio,
    estimate_bpm_and_beats,
    groove_histogram,
    ticks_from_beats,
)
from slowapi.errors import RateLimitExceeded

# Configure logging to flush immediately to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Force flush after each log
for handler in logging.root.handlers:
    handler.flush()

logger = logging.getLogger(__name__)

app = FastAPI(title="Hook-Gen API", version="2.0.0")

# Rate limiting setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]


# CORS: Handle preflight OPTIONS requests manually for maximum compatibility
@app.middleware("http")
async def cors_handler(request: Request, call_next):
    # Handle preflight OPTIONS request immediately
    if request.method == "OPTIONS":
        response = Response(status_code=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, X-Requested-With"
        )
        response.headers["Access-Control-Max-Age"] = "86400"
        return response

    # Process the actual request
    response = await call_next(request)

    # Add CORS headers to all responses
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, X-Requested-With"
    )

    return response


@app.on_event("startup")
def on_startup():
    init_db()

    # Warm up librosa/audio processing
    try:
        logger.info("Warming up audio analysis models...")
        # Create 1 second of silence/noise
        dummy_audio = np.random.uniform(-0.1, 0.1, 22050).astype(np.float32)
        sr = 22050

        # Warm up key detection
        detect_scale_from_audio(dummy_audio, sr)

        # Warm up BPM/rhythm detection
        tempo, beats = estimate_bpm_and_beats(dummy_audio, sr)
        ticks = ticks_from_beats(beats)
        groove_histogram(dummy_audio, sr, ticks)

        logger.info("Audio analysis models warmed up")
    except Exception as e:
        logger.warning(f"Warm-up failed: {e}")

    logger.info("Application started successfully")


# Health check / root endpoint
@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"message": "Hook-Gen API is running", "version": "2.0.0"}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}


app.include_router(endpoints.router)
