import asyncio
import io
import json
import logging
import os
import tempfile
import uuid
from math import isclose
from pathlib import Path
from typing import List, Literal, Optional

import librosa
import numpy as np
import soundfile as sf
from api.errors import ErrorCode, ErrorResponse, create_error_response, create_sse_error
from api.rate_limit import ANALYZE_RATE_LIMIT, GENERATE_RATE_LIMIT, limiter
from app.database import get_session, save_session
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from hookgen_core import (
    detect_scale_from_audio,
    estimate_bpm_and_beats,
    groove_histogram,
    list_available_scales,
    notes_to_midi_bytes,
    ticks_from_beats,
)
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


def get_examples_dir() -> Path:
    """Get the examples directory, checking multiple possible locations."""
    # Check locations in order of preference
    candidates = [
        Path("/app/examples"),  # Docker mount location
        Path(__file__).parent.parent.parent / "hook-aid" / "examples",  # Project root
        Path(__file__).parent.parent / "examples",  # Backend directory
    ]

    for path in candidates:
        if path.exists() and path.is_dir():
            logger.info(f"Using examples directory: {path}")
            return path

    logger.warning(f"No examples directory found. Checked: {[str(p) for p in candidates]}")
    return candidates[0]  # Return first candidate even if not found


EXAMPLES_DIR = get_examples_dir()

# Configuration constants
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB limit
AUDIO_PROCESSING_TIMEOUT_SECONDS = 120  # 120 seconds timeout for audio processing
MAX_AUDIO_DURATION_SECONDS = 8  # Only analyze first 8 seconds (enough for BPM/scale)
MAX_UPLOAD_DURATION_SECONDS = 30  # Reject files longer than 30 seconds
AUDIO_DECODE_TIMEOUT_SECONDS = 45  # Decode timeout
ANALYSIS_TIMEOUT_SECONDS = 45  # Tempo/groove/scale analysis timeout


def fast_load_audio(buffer, max_duration=8):
    """
    Fast audio loading using soundfile directly (much faster than librosa.load).
    Returns mono audio and sample rate.
    """
    buffer.seek(0)
    try:
        # Open as SoundFile to get metadata without reading whole file
        with sf.SoundFile(buffer) as f:
            sr = f.samplerate
            # Calculate frames to read
            max_frames = int(max_duration * sr)
            # Read only the needed frames
            audio = f.read(frames=max_frames, dtype="float32")

            # Convert to mono if stereo
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            return audio, sr
    except Exception:
        # Fallback to librosa for non-WAV formats
        buffer.seek(0)
        return librosa.load(buffer, sr=None, mono=True, duration=max_duration)


# Allowed content types and file extensions
ALLOWED_CONTENT_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/x-mpeg-3",
    "audio/flac",
    "audio/x-flac",
    "audio/ogg",
    "audio/vorbis",
}

ALLOWED_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".flac",
    ".ogg",
    ".m4a",
    ".aac",
}

router = APIRouter()


class GenreInfo(BaseModel):
    tags: List[str]
    confidence: float
    explanation: List[str]
    preset: dict
    debug: Optional[dict] = None


class AnalysisResponse(BaseModel):
    bpm: float
    scale: Optional[str]
    scale_score: float
    histogram: List[float]
    genre: Optional[GenreInfo] = None


class GenerateRequest(BaseModel):
    bpm: float = Field(gt=0, le=300)
    scale: str
    density: int = Field(ge=1, le=16)
    syncopation: float = Field(ge=0.0, le=1.0)
    pitch_register: Literal["low", "mid", "high"]
    histogram: List[float] = Field(min_length=16, max_length=16)
    seed: int

    @validator("histogram")
    def validate_histogram_sum(cls, v):
        """Ensure histogram sums approximately to 1.0"""
        total = sum(v)
        if not isclose(total, 1.0, abs_tol=0.01):
            raise ValueError(f"histogram must sum to approximately 1.0, got {total}")
        return v


class Note(BaseModel):
    pitch: int = Field(ge=0, le=127)  # MIDI number
    start: float = Field(ge=0)  # In beats
    duration: float = Field(gt=0)  # In beats
    velocity: int = Field(100, ge=0, le=127)


class HookResponse(BaseModel):
    hooks: List[List[Note]]


@router.get("/scales")
def get_scales():
    return {"scales": list_available_scales()}


def sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request (bad format, empty file)"},
        408: {"model": ErrorResponse, "description": "Processing timeout"},
        413: {"model": ErrorResponse, "description": "File too large"},
        422: {"model": ErrorResponse, "description": "Unprocessable audio"},
        429: {"model": ErrorResponse, "description": "Rate limited"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
@limiter.limit(ANALYZE_RATE_LIMIT)
async def analyze_audio(request: Request, file: UploadFile = File(...)):  # noqa: B008
    """Non-streaming analyze endpoint."""
    logger.info(f"[ANALYZE-SIMPLE] Request received: {file.filename}, {file.content_type}")

    buffer = None
    try:
        # Validate content type
        if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(f"Rejected file with invalid content-type: {file.content_type}")
            raise create_error_response(
                ErrorCode.UNSUPPORTED_FORMAT,
                details={
                    "content_type": file.content_type,
                    "allowed": sorted(ALLOWED_CONTENT_TYPES),
                },
            )

        # Validate file extension
        if file.filename:
            file_ext = os.path.splitext(file.filename.lower())[1]
            if file_ext not in ALLOWED_EXTENSIONS:
                logger.warning(f"Rejected file with invalid extension: {file_ext}")
                raise create_error_response(
                    ErrorCode.UNSUPPORTED_FORMAT,
                    details={
                        "extension": file_ext,
                        "allowed": sorted(ALLOWED_EXTENSIONS),
                    },
                )

        # Validate file size - use SpooledTemporaryFile to avoid RAM issues with large files
        # Files under 10MB stay in memory, larger ones spill to disk
        tmp_file = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024, mode="w+b")
        total_size = 0
        chunk_size = 1024 * 1024  # 1 MB chunks

        try:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break

                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE_BYTES:
                    tmp_file.close()
                    logger.warning(f"Rejected file exceeding size limit: {total_size} bytes")
                    raise create_error_response(
                        ErrorCode.FILE_TOO_LARGE,
                        details={
                            "size_bytes": total_size,
                            "max_bytes": MAX_FILE_SIZE_BYTES,
                        },
                    )

                tmp_file.write(chunk)

            if total_size == 0:
                tmp_file.close()
                logger.warning("Rejected empty file")
                raise create_error_response(ErrorCode.EMPTY_FILE)

            tmp_file.seek(0)
            buffer = io.BytesIO(tmp_file.read())
            tmp_file.close()
            logger.info(f"[ANALYZE-SIMPLE] File loaded into buffer: {total_size} bytes")
        except HTTPException:
            raise
        except Exception as e:
            tmp_file.close()
            raise create_error_response(
                ErrorCode.INTERNAL_ERROR,
                message=f"Failed to read file: {e}",
                log_level="error",
            ) from e

        # Wrap audio processing in a timeout to prevent hangs
        async def process_audio():
            loop = asyncio.get_running_loop()

            # Check full file duration before processing
            def check_duration():
                buffer.seek(0)
                try:
                    with sf.SoundFile(buffer) as f:
                        full_duration = len(f) / f.samplerate
                    buffer.seek(0)
                    return full_duration
                except Exception:
                    buffer.seek(0)
                    return None

            full_duration = await loop.run_in_executor(None, check_duration)
            if full_duration is not None and full_duration > MAX_UPLOAD_DURATION_SECONDS:
                logger.warning(
                    f"Rejected file exceeding duration limit: {file.filename}, "
                    f"duration={full_duration:.1f}s"
                )
                raise create_error_response(
                    ErrorCode.DURATION_TOO_LONG,
                    details={
                        "duration_seconds": round(full_duration, 1),
                        "max_seconds": MAX_UPLOAD_DURATION_SECONDS,
                    },
                )

            logger.info("[ANALYZE-SIMPLE] Starting audio decode (fast path)...")

            # Use fast_load_audio which uses soundfile directly for WAV files
            audio_array, sample_rate = await loop.run_in_executor(
                None, lambda: fast_load_audio(buffer, MAX_AUDIO_DURATION_SECONDS)
            )
            logger.info(
                f"[ANALYZE-SIMPLE] Decoded: {len(audio_array)} samples @ {sample_rate}Hz"
            )

            # Process audio analysis
            logger.info("[ANALYZE-SIMPLE] Starting BPM detection...")
            detected_bpm, beat_times = await loop.run_in_executor(
                None, lambda: estimate_bpm_and_beats(audio_array, sample_rate)
            )
            logger.info(f"[ANALYZE-SIMPLE] BPM: {detected_bpm}, beats: {len(beat_times)}")

            ticks = ticks_from_beats(beat_times, subdiv=4)
            histogram = await loop.run_in_executor(
                None, lambda: groove_histogram(audio_array, sample_rate, ticks)
            )

            if histogram is None or not np.asarray(histogram).size or not np.any(histogram):
                histogram = (np.ones(16) / 16.0).tolist()
            else:
                histogram = histogram.tolist()

            suggested_scale, suggested_score = await loop.run_in_executor(
                None, lambda: detect_scale_from_audio(audio_array, sample_rate)
            )

            # Genre classification with improved error handling
            genre_info = None
            try:
                from hookgen_core import classify_genre

                genre_result = await loop.run_in_executor(
                    None,
                    lambda: classify_genre(
                        bpm=detected_bpm if detected_bpm else 120.0, histogram=np.asarray(histogram)
                    ),
                )
                genre_info = GenreInfo(
                    tags=genre_result.tags,
                    confidence=genre_result.confidence,
                    explanation=genre_result.explanation,
                    preset=genre_result.preset,
                    debug=genre_result.debug if os.getenv("DEBUG_GENRE") == "true" else None,
                )
            except (ValueError, TypeError) as e:
                # Parameter/type errors - log warning, continue without genre
                logger.warning(f"Genre classification parameter error: {e}")
                genre_info = None
            except np.linalg.LinAlgError as e:
                # Numpy linear algebra errors - log warning, continue
                logger.warning(f"Genre classification numpy error: {e}")
                genre_info = None
            except Exception as e:
                # Unexpected errors - log error level for investigation
                logger.error(f"Genre classification failed unexpectedly: {e}", exc_info=True)
                genre_info = None

            return AnalysisResponse(
                bpm=detected_bpm if detected_bpm else 120.0,
                scale=suggested_scale,
                scale_score=suggested_score,
                histogram=histogram,
                genre=genre_info,
            )

        try:
            result = await asyncio.wait_for(
                process_audio(), timeout=AUDIO_PROCESSING_TIMEOUT_SECONDS
            )
            return result
        except asyncio.TimeoutError:
            logger.error(
                f"Audio processing timed out after {AUDIO_PROCESSING_TIMEOUT_SECONDS} seconds"
            )
            raise create_error_response(
                ErrorCode.PROCESSING_TIMEOUT,
                details={"timeout_seconds": AUDIO_PROCESSING_TIMEOUT_SECONDS},
            ) from None
        except Exception as e:
            # Handle librosa and audio processing errors
            error_msg = str(e)
            logger.error(f"Error processing audio file: {error_msg}", exc_info=True)

            # Check for common librosa errors
            if "NoBackendError" in error_msg or "could not be loaded" in error_msg.lower():
                raise create_error_response(
                    ErrorCode.ANALYSIS_FAILED,
                    message="Unsupported audio format or corrupted file. "
                    "Please ensure the file is a valid audio file.",
                ) from None

            raise create_error_response(
                ErrorCode.ANALYSIS_FAILED,
                message=f"Failed to process audio file: {error_msg}",
            ) from e

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, timeouts, etc.)
        raise
    except Exception:
        # Catch any other unexpected errors
        logger.exception("Unhandled error processing audio request")
        raise create_error_response(ErrorCode.INTERNAL_ERROR, log_level="error") from None
    finally:
        # Ensure resources are cleaned up
        if buffer is not None:
            try:
                buffer.close()
            except Exception:
                pass

        # Ensure the file is closed
        try:
            await file.close()
        except Exception:
            pass


@router.post("/analyze/stream")
@limiter.limit(ANALYZE_RATE_LIMIT)
async def analyze_audio_stream(request: Request, file: UploadFile = File(...)):  # noqa: B008
    """
    Streaming analyze endpoint that sends progress updates via Server-Sent Events.

    Events:
    - progress: {stage: string, progress: number (0-100), message: string}
    - result: {bpm, scale, scale_score, histogram}
    - error: {detail: string}
    """
    logger.info(f"[ANALYZE] Request received: {file.filename}, {file.content_type}")

    async def generate_events():
        buffer = None
        try:
            logger.info("[ANALYZE] Generator started")
            # Stage 1: Validating file (0-10%)
            yield sse_event(
                "progress", {"stage": "validating", "progress": 0, "message": "Validating file..."}
            )

            # Validate content type
            if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
                yield sse_event(
                    "error",
                    create_sse_error(
                        ErrorCode.UNSUPPORTED_FORMAT,
                        details={
                            "content_type": file.content_type,
                            "allowed": sorted(ALLOWED_CONTENT_TYPES),
                        },
                    ),
                )
                return

            # Validate file extension
            if file.filename:
                file_ext = os.path.splitext(file.filename.lower())[1]
                if file_ext not in ALLOWED_EXTENSIONS:
                    yield sse_event(
                        "error",
                        create_sse_error(
                            ErrorCode.UNSUPPORTED_FORMAT,
                            details={
                                "extension": file_ext,
                                "allowed": sorted(ALLOWED_EXTENSIONS),
                            },
                        ),
                    )
                    return

            yield sse_event(
                "progress", {"stage": "uploading", "progress": 5, "message": "Reading file..."}
            )

            # Read file contents using SpooledTemporaryFile to avoid RAM issues
            # Files under 10MB stay in memory, larger ones spill to disk
            tmp_file = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024, mode="w+b")
            total_size = 0
            chunk_size = 1024 * 1024

            try:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break

                    total_size += len(chunk)
                    if total_size > MAX_FILE_SIZE_BYTES:
                        tmp_file.close()
                        yield sse_event(
                            "error",
                            create_sse_error(
                                ErrorCode.FILE_TOO_LARGE,
                                details={
                                    "size_bytes": total_size,
                                    "max_bytes": MAX_FILE_SIZE_BYTES,
                                },
                            ),
                        )
                        return

                    tmp_file.write(chunk)

                if total_size == 0:
                    tmp_file.close()
                    yield sse_event("error", create_sse_error(ErrorCode.EMPTY_FILE))
                    return

                tmp_file.seek(0)
                buffer = io.BytesIO(tmp_file.read())
                tmp_file.close()
            except Exception as e:
                tmp_file.close()
                logger.error(f"Failed to read uploaded file: {e}")
                yield sse_event(
                    "error",
                    create_sse_error(
                        ErrorCode.INTERNAL_ERROR,
                        message=f"Failed to read file: {e}",
                    ),
                )
                return

            # Check full file duration before processing
            loop = asyncio.get_running_loop()

            def check_duration():
                buffer.seek(0)
                try:
                    with sf.SoundFile(buffer) as f:
                        full_duration = len(f) / f.samplerate
                    buffer.seek(0)
                    return full_duration
                except Exception:
                    buffer.seek(0)
                    return None

            full_duration = await loop.run_in_executor(None, check_duration)
            if full_duration is not None and full_duration > MAX_UPLOAD_DURATION_SECONDS:
                logger.warning(
                    f"Rejected file exceeding duration limit: {file.filename}, "
                    f"duration={full_duration:.1f}s"
                )
                yield sse_event(
                    "error",
                    create_sse_error(
                        ErrorCode.DURATION_TOO_LONG,
                        details={
                            "duration_seconds": round(full_duration, 1),
                            "max_seconds": MAX_UPLOAD_DURATION_SECONDS,
                        },
                    ),
                )
                return

            # Stage 2: Loading audio (10-30%)
            yield sse_event(
                "progress", {"stage": "loading", "progress": 10, "message": "Decoding audio..."}
            )

            logger.info(f"Starting audio decode: {total_size} bytes, filename={file.filename}")

            try:
                # Use fast_load_audio which uses soundfile directly (much faster)
                audio_array, sample_rate = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, lambda: fast_load_audio(buffer, MAX_AUDIO_DURATION_SECONDS)
                    ),
                    timeout=AUDIO_DECODE_TIMEOUT_SECONDS,
                )
                logger.info(
                    f"Audio decoded successfully: {len(audio_array)} samples at {sample_rate}Hz"
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Audio decode timed out after {AUDIO_DECODE_TIMEOUT_SECONDS}s "
                    f"for file: {file.filename}"
                )
                yield sse_event(
                    "error",
                    create_sse_error(
                        ErrorCode.PROCESSING_TIMEOUT,
                        message=f"Audio decoding timed out after {AUDIO_DECODE_TIMEOUT_SECONDS}s. "
                        "Try a shorter or smaller file.",
                        details={"timeout_seconds": AUDIO_DECODE_TIMEOUT_SECONDS},
                    ),
                )
                return
            except Exception as e:
                error_msg = str(e)
                logger.error(
                    f"Audio decode failed for {file.filename}: {error_msg}",
                    exc_info=True,
                )
                if "NoBackendError" in error_msg or "could not be loaded" in error_msg.lower():
                    yield sse_event(
                        "error",
                        create_sse_error(
                            ErrorCode.ANALYSIS_FAILED,
                            message="Unsupported audio format or corrupted file. "
                            "Make sure ffmpeg is installed for MP3/M4A support.",
                        ),
                    )
                else:
                    yield sse_event(
                        "error",
                        create_sse_error(
                            ErrorCode.ANALYSIS_FAILED,
                            message=f"Failed to decode audio: {error_msg}",
                        ),
                    )
                return

            # Stage 3: Detecting tempo (30-55%)
            yield sse_event(
                "progress", {"stage": "tempo", "progress": 30, "message": "Detecting tempo..."}
            )

            logger.info(f"Starting tempo detection for {len(audio_array)} samples")
            try:
                detected_bpm, beat_times = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, lambda: estimate_bpm_and_beats(audio_array, sample_rate)
                    ),
                    timeout=ANALYSIS_TIMEOUT_SECONDS,
                )
                logger.info(f"Tempo detected: {detected_bpm} BPM, {len(beat_times)} beats")
            except asyncio.TimeoutError:
                logger.error(f"Tempo detection timed out after {ANALYSIS_TIMEOUT_SECONDS}s")
                yield sse_event(
                    "error",
                    create_sse_error(
                        ErrorCode.PROCESSING_TIMEOUT,
                        message=f"Tempo detection timed out after {ANALYSIS_TIMEOUT_SECONDS}s",
                        details={"timeout_seconds": ANALYSIS_TIMEOUT_SECONDS, "stage": "tempo"},
                    ),
                )
                return

            yield sse_event(
                "progress",
                {
                    "stage": "tempo",
                    "progress": 55,
                    "message": f"Found tempo: {round(detected_bpm) if detected_bpm else 120} BPM",
                },
            )

            # Stage 4: Analyzing groove (55-75%)
            yield sse_event(
                "progress",
                {"stage": "groove", "progress": 55, "message": "Analyzing groove pattern..."},
            )

            ticks = ticks_from_beats(beat_times, subdiv=4)

            logger.info("Starting groove analysis")
            try:
                histogram = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, lambda: groove_histogram(audio_array, sample_rate, ticks)
                    ),
                    timeout=ANALYSIS_TIMEOUT_SECONDS,
                )
                logger.info("Groove analysis complete")
            except asyncio.TimeoutError:
                logger.error(f"Groove analysis timed out after {ANALYSIS_TIMEOUT_SECONDS}s")
                yield sse_event(
                    "error",
                    create_sse_error(
                        ErrorCode.PROCESSING_TIMEOUT,
                        message=f"Groove analysis timed out after {ANALYSIS_TIMEOUT_SECONDS}s",
                        details={"timeout_seconds": ANALYSIS_TIMEOUT_SECONDS, "stage": "groove"},
                    ),
                )
                return

            if histogram is None or not np.asarray(histogram).size or not np.any(histogram):
                histogram = (np.ones(16) / 16.0).tolist()
            else:
                histogram = histogram.tolist()

            yield sse_event(
                "progress",
                {"stage": "groove", "progress": 75, "message": "Groove pattern captured"},
            )

            # Stage 5: Detecting key/scale (75-95%)
            yield sse_event(
                "progress",
                {"stage": "scale", "progress": 75, "message": "Detecting musical key..."},
            )

            logger.info("Starting scale detection")
            try:
                suggested_scale, suggested_score = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, lambda: detect_scale_from_audio(audio_array, sample_rate)
                    ),
                    timeout=ANALYSIS_TIMEOUT_SECONDS,
                )
                logger.info(f"Scale detected: {suggested_scale} (score: {suggested_score})")
            except asyncio.TimeoutError:
                logger.error(f"Scale detection timed out after {ANALYSIS_TIMEOUT_SECONDS}s")
                yield sse_event(
                    "error",
                    create_sse_error(
                        ErrorCode.PROCESSING_TIMEOUT,
                        message=f"Scale detection timed out after {ANALYSIS_TIMEOUT_SECONDS}s",
                        details={"timeout_seconds": ANALYSIS_TIMEOUT_SECONDS, "stage": "scale"},
                    ),
                )
                return

            yield sse_event(
                "progress",
                {
                    "stage": "scale",
                    "progress": 95,
                    "message": (
                        f"Detected key: {suggested_scale}"
                        if suggested_scale
                        else "Key detection complete"
                    ),
                },
            )

            # Stage 6: Genre classification (95-98%)
            yield sse_event(
                "progress",
                {"stage": "genre", "progress": 95, "message": "Classifying rhythm style..."},
            )

            genre_info = None
            try:
                from hookgen_core import classify_genre

                genre_result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: classify_genre(
                            bpm=detected_bpm if detected_bpm else 120.0,
                            histogram=np.asarray(histogram),
                        ),
                    ),
                    timeout=ANALYSIS_TIMEOUT_SECONDS,
                )
                genre_info = {
                    "tags": genre_result.tags,
                    "confidence": genre_result.confidence,
                    "explanation": genre_result.explanation,
                    "preset": genre_result.preset,
                }
                logger.info(f"Genre classified: {genre_result.tags}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Genre classification parameter error: {e}")
                genre_info = None
            except np.linalg.LinAlgError as e:
                logger.warning(f"Genre classification numpy error: {e}")
                genre_info = None
            except Exception as e:
                logger.error(f"Genre classification failed unexpectedly: {e}", exc_info=True)
                genre_info = None

            # Stage 7: Complete (100%)
            yield sse_event(
                "progress", {"stage": "complete", "progress": 100, "message": "Analysis complete!"}
            )

            # Send final result
            result_data = {
                "bpm": detected_bpm if detected_bpm else 120.0,
                "scale": suggested_scale,
                "scale_score": suggested_score,
                "histogram": histogram,
            }
            if genre_info:
                result_data["genre"] = genre_info

            yield sse_event("result", result_data)

        except Exception:
            logger.exception("Unhandled error in streaming analyze")
            yield sse_event("error", create_sse_error(ErrorCode.INTERNAL_ERROR))
        finally:
            if buffer is not None:
                try:
                    buffer.close()
                except Exception:
                    pass
            try:
                await file.close()
            except Exception:
                pass

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/generate",
    response_model=HookResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Invalid request data"},
        429: {"model": ErrorResponse, "description": "Rate limited"},
        500: {"model": ErrorResponse, "description": "Generation failed"},
    },
)
@limiter.limit(GENERATE_RATE_LIMIT)
def generate_hooks(request: Request, req: GenerateRequest):
    reg_map = {"low": (48, 69), "mid": (55, 76), "high": (62, 84)}
    register_range = reg_map.get(req.pitch_register, (55, 76))

    hooks = []
    base_seed = req.seed

    # Convert list to numpy array for the function
    hist_array = np.array(req.histogram)

    # Import from shared library
    from hookgen_core import generate_structured_hook

    for i in range(5):
        current_seed = base_seed + i

        # Generate 4-bar structured hook
        notes_data = generate_structured_hook(
            histogram=hist_array,
            scale=req.scale,
            register=register_range,
            density=req.density,
            syncopation=req.syncopation,
            seed=current_seed,
        )

        formatted_notes = []
        for n in notes_data:
            formatted_notes.append(
                Note(
                    pitch=n["pitch"],
                    start=n["start"] / 4.0,  # Convert 16th steps to beats
                    duration=n["duration"] / 4.0,  # Convert 16th steps to beats
                    velocity=n["velocity"],
                )
            )
        hooks.append(formatted_notes)

    return HookResponse(hooks=hooks)


class MidiRequest(BaseModel):
    notes: List[Note]
    bpm: float = Field(gt=0, le=300)


@router.post("/export/midi")
def export_midi(req: MidiRequest):
    # Convert beats back to 16th steps for export.py
    # export.py expects (onset, duration, pitch) where onset/duration are in 16th steps
    midi_notes = []
    for n in req.notes:
        onset = int(round(n.start * 4))
        duration = int(round(n.duration * 4))
        midi_notes.append((onset, duration, n.pitch))

    midi_bytes = notes_to_midi_bytes(midi_notes, bpm=req.bpm)

    return Response(
        content=midi_bytes,
        media_type="audio/midi",
        headers={"Content-Disposition": "attachment; filename=hook.mid"},
    )


class SessionData(GenerateRequest):
    pass


@router.post("/session/save")
def save_session_endpoint(data: SessionData):
    session_id = str(uuid.uuid4())
    save_session(session_id, data.dict())
    return {"id": session_id}


@router.get(
    "/session/{session_id}",
    responses={404: {"model": ErrorResponse, "description": "Session not found"}},
)
def get_session_endpoint(session_id: str):
    data = get_session(session_id)
    if not data:
        raise create_error_response(ErrorCode.NOT_FOUND, message="Session not found")
    return data


# ===== Example Files Endpoints =====


class ExampleFile(BaseModel):
    name: str
    filename: str
    description: str


def parse_example_filename(filename: str) -> dict:
    """Parse example filename like 'groove_100bpm.wav' into metadata."""
    name = filename.replace(".wav", "").replace("_", " ").title()

    # Extract BPM if present
    bpm_part = ""
    for part in filename.replace(".wav", "").split("_"):
        if "bpm" in part.lower():
            bpm_part = part.replace("bpm", " BPM")
            break

    # Create human-readable description
    base_name = filename.replace(".wav", "")
    descriptions = {
        "groove_100bpm": "Funky groove pattern",
        "groove_100bpm_long": "Extended groove pattern",
        "straight_120bpm": "Straight 4/4 beat",
        "fouronthefloor_124bpm": "Classic house kick pattern",
        "shuffle_92bpm": "Shuffled swing feel",
        "halftime_70bpm": "Half-time feel",
        "reggaeton_96bpm": "Reggaeton dembow rhythm",
        "brokenbeat_128bpm": "Syncopated broken beat",
        "bass_cminor_90bpm": "C minor bass groove",
        "keys_eminor_100bpm": "E minor keys loop",
        "plucks_gmajor_110bpm": "G major pluck synth",
    }
    description = descriptions.get(
        base_name,
        f"Example loop at {bpm_part}" if bpm_part else "Example drum loop",
    )

    return {"name": name, "description": description}


@router.get("/examples")
def list_examples() -> List[ExampleFile]:
    """List all available example drum loops."""
    # Re-check the directory at request time in case it was mounted after startup
    examples_dir = get_examples_dir()

    if not examples_dir.exists():
        logger.warning(f"Examples directory not found: {examples_dir}")
        return []

    examples = []
    for f in sorted(examples_dir.glob("*.wav")):
        meta = parse_example_filename(f.name)
        examples.append(
            ExampleFile(name=meta["name"], filename=f.name, description=meta["description"])
        )

    logger.info(f"Found {len(examples)} example files in {examples_dir}")
    return examples


@router.get(
    "/examples/{filename}",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid filename"},
        404: {"model": ErrorResponse, "description": "File not found"},
    },
)
async def get_example_file(filename: str):
    """Serve an example audio file."""
    # Security: only allow .wav files and prevent path traversal
    if not filename.endswith(".wav") or "/" in filename or "\\" in filename:
        raise create_error_response(ErrorCode.INVALID_FILENAME)

    examples_dir = get_examples_dir()
    filepath = examples_dir / filename
    if not filepath.exists() or not filepath.is_file():
        raise create_error_response(ErrorCode.NOT_FOUND, message="Example file not found")

    return FileResponse(path=filepath, media_type="audio/wav", filename=filename)


@router.post(
    "/examples/{filename}/analyze",
    response_model=AnalysisResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid filename"},
        404: {"model": ErrorResponse, "description": "File not found"},
        500: {"model": ErrorResponse, "description": "Analysis failed"},
    },
)
async def analyze_example(filename: str):
    """Analyze an example file directly (saves client from downloading first)."""
    # Security: only allow .wav files and prevent path traversal
    if not filename.endswith(".wav") or "/" in filename or "\\" in filename:
        raise create_error_response(ErrorCode.INVALID_FILENAME)

    examples_dir = get_examples_dir()
    filepath = examples_dir / filename
    if not filepath.exists() or not filepath.is_file():
        raise create_error_response(ErrorCode.NOT_FOUND, message="Example file not found")

    try:
        loop = asyncio.get_running_loop()

        # Load audio file efficiently
        def load_example_fast():
            # Use soundfile for fast partial reading
            with sf.SoundFile(str(filepath)) as f:
                sr = f.samplerate
                max_frames = int(MAX_AUDIO_DURATION_SECONDS * sr)
                audio = f.read(frames=max_frames, dtype="float32")
                if len(audio.shape) > 1:
                    audio = audio.mean(axis=1)
                return audio, sr

        audio_array, sample_rate = await loop.run_in_executor(None, load_example_fast)

        # Process audio analysis
        detected_bpm, beat_times = await loop.run_in_executor(
            None, lambda: estimate_bpm_and_beats(audio_array, sample_rate)
        )

        ticks = ticks_from_beats(beat_times, subdiv=4)
        histogram = await loop.run_in_executor(
            None, lambda: groove_histogram(audio_array, sample_rate, ticks)
        )

        if histogram is None or not np.asarray(histogram).size or not np.any(histogram):
            histogram = (np.ones(16) / 16.0).tolist()
        else:
            histogram = histogram.tolist()

        suggested_scale, suggested_score = await loop.run_in_executor(
            None, lambda: detect_scale_from_audio(audio_array, sample_rate)
        )

        return AnalysisResponse(
            bpm=detected_bpm if detected_bpm else 120.0,
            scale=suggested_scale,
            scale_score=suggested_score,
            histogram=histogram,
        )
    except Exception as e:
        logger.error(f"Error analyzing example file: {e}", exc_info=True)
        raise create_error_response(
            ErrorCode.ANALYSIS_FAILED,
            message=f"Failed to analyze example: {str(e)}",
            log_level="error",
        ) from e
