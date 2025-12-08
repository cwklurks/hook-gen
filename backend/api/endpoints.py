from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal
import io
import librosa
import numpy as np
from math import isclose
import logging
import asyncio
import os
import json
from pathlib import Path

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
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB default
AUDIO_PROCESSING_TIMEOUT_SECONDS = 120  # 120 seconds timeout for audio processing
MAX_AUDIO_DURATION_SECONDS = 10  # Only analyze first 10 seconds (enough for BPM/scale)
AUDIO_DECODE_TIMEOUT_SECONDS = 60  # Decoding is CPU-intensive, especially on shared hosting
ANALYSIS_TIMEOUT_SECONDS = 60  # Tempo/groove/scale analysis timeout

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

# Import from the app package
# Note: This assumes running from backend/ directory or proper python path
from app.rhythm import estimate_bpm_and_beats, ticks_from_beats, groove_histogram
from app.motif import sample_rhythm, detect_scale_from_audio, list_available_scales

router = APIRouter()

class AnalysisResponse(BaseModel):
    bpm: float
    scale: Optional[str]
    scale_score: float
    histogram: List[float]

class GenerateRequest(BaseModel):
    bpm: float = Field(gt=0, le=300)
    scale: str
    density: int = Field(ge=1, le=10)
    syncopation: float = Field(ge=0.0, le=1.0)
    pitch_register: Literal["low", "mid", "high"]
    histogram: List[float] = Field(min_items=16, max_items=16)
    seed: int
    
    @validator('histogram')
    def validate_histogram_sum(cls, v):
        """Ensure histogram sums approximately to 1.0"""
        total = sum(v)
        if not isclose(total, 1.0, abs_tol=0.01):
            raise ValueError(f'histogram must sum to approximately 1.0, got {total}')
        return v

class Note(BaseModel):
    pitch: int = Field(ge=0, le=127)  # MIDI number
    start: float = Field(ge=0)  # In beats
    duration: float = Field(gt=0) # In beats
    velocity: int = Field(ge=0, le=127)

class HookResponse(BaseModel):
    hooks: List[List[Note]]

@router.get("/scales")
def get_scales():
    return {"scales": list_available_scales()}

def sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_audio(file: UploadFile = File(...)):
    """Non-streaming analyze endpoint for backwards compatibility."""
    buffer = None
    try:
        # Validate content type
        if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
            logger.warning(f"Rejected file with invalid content-type: {file.content_type}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content type. Allowed types: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
            )
        
        # Validate file extension
        if file.filename:
            file_ext = os.path.splitext(file.filename.lower())[1]
            if file_ext not in ALLOWED_EXTENSIONS:
                logger.warning(f"Rejected file with invalid extension: {file_ext}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file extension. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                )
        
        # Validate file size - read in chunks to enforce limit
        contents = bytearray()
        total_size = 0
        chunk_size = 1024 * 1024  # 1 MB chunks
        
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            
            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE_BYTES:
                logger.warning(f"Rejected file exceeding size limit: {total_size} bytes")
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size: {MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB"
                )
            
            contents.extend(chunk)
        
        if total_size == 0:
            logger.warning("Rejected empty file")
            raise HTTPException(status_code=400, detail="File is empty")
        
        buffer = io.BytesIO(contents)
        
        # Wrap audio processing in a timeout to prevent hangs
        async def process_audio():
            # Run librosa.load in executor since it's CPU-bound
            # Only load first N seconds for faster processing
            loop = asyncio.get_event_loop()
            audio_array, sample_rate = await loop.run_in_executor(
                None,
                lambda: librosa.load(buffer, sr=22050, mono=True, duration=MAX_AUDIO_DURATION_SECONDS)
            )
            
            # Process audio analysis
            detected_bpm, beat_times = await loop.run_in_executor(
                None,
                lambda: estimate_bpm_and_beats(audio_array, sample_rate)
            )
            
            ticks = ticks_from_beats(beat_times, subdiv=4)
            histogram = await loop.run_in_executor(
                None,
                lambda: groove_histogram(audio_array, sample_rate, ticks)
            )
            
            if histogram is None or not np.asarray(histogram).size or not np.any(histogram):
                histogram = (np.ones(16) / 16.0).tolist()
            else:
                histogram = histogram.tolist()
            
            suggested_scale, suggested_score = await loop.run_in_executor(
                None,
                lambda: detect_scale_from_audio(audio_array, sample_rate)
            )
            
            return AnalysisResponse(
                bpm=detected_bpm if detected_bpm else 120.0,
                scale=suggested_scale,
                scale_score=suggested_score,
                histogram=histogram
            )
        
        try:
            result = await asyncio.wait_for(
                process_audio(),
                timeout=AUDIO_PROCESSING_TIMEOUT_SECONDS
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Audio processing timed out after {AUDIO_PROCESSING_TIMEOUT_SECONDS} seconds")
            raise HTTPException(
                status_code=408,
                detail=f"Audio processing timed out. Maximum processing time: {AUDIO_PROCESSING_TIMEOUT_SECONDS} seconds"
            )
        except Exception as e:
            # Handle librosa and audio processing errors
            error_msg = str(e)
            logger.error(f"Error processing audio file: {error_msg}", exc_info=True)
            
            # Check for common librosa errors
            if "NoBackendError" in error_msg or "could not be loaded" in error_msg.lower():
                raise HTTPException(
                    status_code=422,
                    detail="Unsupported audio format or corrupted file. Please ensure the file is a valid audio file."
                )
            
            raise HTTPException(
                status_code=422,
                detail=f"Failed to process audio file: {error_msg}"
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, timeouts, etc.)
        raise
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception("Unhandled error processing audio request")
        raise HTTPException(status_code=500, detail="Internal server error")
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
async def analyze_audio_stream(file: UploadFile = File(...)):
    """
    Streaming analyze endpoint that sends progress updates via Server-Sent Events.
    
    Events:
    - progress: {stage: string, progress: number (0-100), message: string}
    - result: {bpm, scale, scale_score, histogram}
    - error: {detail: string}
    """
    async def generate_events():
        buffer = None
        try:
            # Stage 1: Validating file (0-10%)
            yield sse_event("progress", {
                "stage": "validating",
                "progress": 0,
                "message": "Validating file..."
            })
            
            # Validate content type
            if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
                yield sse_event("error", {
                    "detail": f"Invalid content type. Allowed types: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
                })
                return
            
            # Validate file extension
            if file.filename:
                file_ext = os.path.splitext(file.filename.lower())[1]
                if file_ext not in ALLOWED_EXTENSIONS:
                    yield sse_event("error", {
                        "detail": f"Invalid file extension. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                    })
                    return
            
            yield sse_event("progress", {
                "stage": "uploading",
                "progress": 5,
                "message": "Reading file..."
            })
            
            # Read file contents
            contents = bytearray()
            total_size = 0
            chunk_size = 1024 * 1024
            
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE_BYTES:
                    yield sse_event("error", {
                        "detail": f"File too large. Maximum size: {MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB"
                    })
                    return
                
                contents.extend(chunk)
            
            if total_size == 0:
                yield sse_event("error", {"detail": "File is empty"})
                return
            
            buffer = io.BytesIO(contents)
            
            # Stage 2: Loading audio (10-30%)
            yield sse_event("progress", {
                "stage": "loading",
                "progress": 10,
                "message": "Decoding audio..."
            })
            
            logger.info(f"Starting audio decode: {total_size} bytes, filename={file.filename}")
            loop = asyncio.get_event_loop()
            
            try:
                audio_array, sample_rate = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: librosa.load(buffer, sr=22050, mono=True, duration=MAX_AUDIO_DURATION_SECONDS)
                    ),
                    timeout=AUDIO_DECODE_TIMEOUT_SECONDS
                )
                logger.info(f"Audio decoded successfully: {len(audio_array)} samples at {sample_rate}Hz")
            except asyncio.TimeoutError:
                logger.error(f"Audio decode timed out after {AUDIO_DECODE_TIMEOUT_SECONDS}s for file: {file.filename}")
                yield sse_event("error", {"detail": f"Audio decoding timed out after {AUDIO_DECODE_TIMEOUT_SECONDS}s. Try a shorter or smaller file."})
                return
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Audio decode failed for {file.filename}: {error_msg}", exc_info=True)
                if "NoBackendError" in error_msg or "could not be loaded" in error_msg.lower():
                    yield sse_event("error", {
                        "detail": "Unsupported audio format or corrupted file. Make sure ffmpeg is installed for MP3/M4A support."
                    })
                else:
                    yield sse_event("error", {"detail": f"Failed to decode audio: {error_msg}"})
                return
            
            # Stage 3: Detecting tempo (30-55%)
            yield sse_event("progress", {
                "stage": "tempo",
                "progress": 30,
                "message": "Detecting tempo..."
            })
            
            logger.info(f"Starting tempo detection for {len(audio_array)} samples")
            try:
                detected_bpm, beat_times = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: estimate_bpm_and_beats(audio_array, sample_rate)
                    ),
                    timeout=ANALYSIS_TIMEOUT_SECONDS
                )
                logger.info(f"Tempo detected: {detected_bpm} BPM, {len(beat_times)} beats")
            except asyncio.TimeoutError:
                logger.error(f"Tempo detection timed out after {ANALYSIS_TIMEOUT_SECONDS}s")
                yield sse_event("error", {"detail": f"Tempo detection timed out after {ANALYSIS_TIMEOUT_SECONDS}s"})
                return
            
            yield sse_event("progress", {
                "stage": "tempo",
                "progress": 55,
                "message": f"Found tempo: {round(detected_bpm) if detected_bpm else 120} BPM"
            })
            
            # Stage 4: Analyzing groove (55-75%)
            yield sse_event("progress", {
                "stage": "groove",
                "progress": 55,
                "message": "Analyzing groove pattern..."
            })
            
            ticks = ticks_from_beats(beat_times, subdiv=4)
            
            logger.info("Starting groove analysis")
            try:
                histogram = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: groove_histogram(audio_array, sample_rate, ticks)
                    ),
                    timeout=ANALYSIS_TIMEOUT_SECONDS
                )
                logger.info("Groove analysis complete")
            except asyncio.TimeoutError:
                logger.error(f"Groove analysis timed out after {ANALYSIS_TIMEOUT_SECONDS}s")
                yield sse_event("error", {"detail": f"Groove analysis timed out after {ANALYSIS_TIMEOUT_SECONDS}s"})
                return
            
            if histogram is None or not np.asarray(histogram).size or not np.any(histogram):
                histogram = (np.ones(16) / 16.0).tolist()
            else:
                histogram = histogram.tolist()
            
            yield sse_event("progress", {
                "stage": "groove",
                "progress": 75,
                "message": "Groove pattern captured"
            })
            
            # Stage 5: Detecting key/scale (75-95%)
            yield sse_event("progress", {
                "stage": "scale",
                "progress": 75,
                "message": "Detecting musical key..."
            })
            
            logger.info("Starting scale detection")
            try:
                suggested_scale, suggested_score = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: detect_scale_from_audio(audio_array, sample_rate)
                    ),
                    timeout=ANALYSIS_TIMEOUT_SECONDS
                )
                logger.info(f"Scale detected: {suggested_scale} (score: {suggested_score})")
            except asyncio.TimeoutError:
                logger.error(f"Scale detection timed out after {ANALYSIS_TIMEOUT_SECONDS}s")
                yield sse_event("error", {"detail": f"Scale detection timed out after {ANALYSIS_TIMEOUT_SECONDS}s"})
                return
            
            yield sse_event("progress", {
                "stage": "scale",
                "progress": 95,
                "message": f"Detected key: {suggested_scale}" if suggested_scale else "Key detection complete"
            })
            
            # Stage 6: Complete (100%)
            yield sse_event("progress", {
                "stage": "complete",
                "progress": 100,
                "message": "Analysis complete!"
            })
            
            # Send final result
            yield sse_event("result", {
                "bpm": detected_bpm if detected_bpm else 120.0,
                "scale": suggested_scale,
                "scale_score": suggested_score,
                "histogram": histogram
            })
            
        except Exception as e:
            logger.exception("Unhandled error in streaming analyze")
            yield sse_event("error", {"detail": "Internal server error"})
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
        }
    )

@router.post("/generate", response_model=HookResponse)
def generate_hooks(req: GenerateRequest):
    reg_map = {"low": (48, 69), "mid": (55, 76), "high": (62, 84)}
    register_range = reg_map.get(req.pitch_register, (55, 76))
    
    hooks = []
    base_seed = req.seed
    
    # Convert list to numpy array for the function
    hist_array = np.array(req.histogram)
    
    # Import the new function
    from app.motif import generate_structured_hook
    
    for i in range(5):
        current_seed = base_seed + i
        
        # Generate 4-bar structured hook
        notes_data = generate_structured_hook(
            histogram=hist_array,
            scale=req.scale,
            register=register_range,
            density=req.density,
            syncopation=req.syncopation,
            seed=current_seed
        )
        
        formatted_notes = []
        for n in notes_data:
            formatted_notes.append(Note(
                pitch=n["pitch"],
                start=n["start"] / 4.0,  # Convert 16th steps to beats
                duration=n["duration"] / 4.0, # Convert 16th steps to beats
                velocity=n["velocity"]
            ))
        hooks.append(formatted_notes)
        
    return HookResponse(hooks=hooks)

class MidiRequest(BaseModel):
    notes: List[Note]
    bpm: float = Field(gt=0, le=300)

from fastapi.responses import Response
from app.export import notes_to_midi_bytes

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
        headers={"Content-Disposition": "attachment; filename=hook.mid"}
    )

import uuid
from app.database import save_session, get_session

class SessionData(GenerateRequest):
    pass

@router.post("/session/save")
def save_session_endpoint(data: SessionData):
    session_id = str(uuid.uuid4())
    save_session(session_id, data.dict())
    return {"id": session_id}

@router.get("/session/{session_id}")
def get_session_endpoint(session_id: str):
    data = get_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
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
    description = descriptions.get(base_name, f"Example loop at {bpm_part}" if bpm_part else "Example drum loop")
    
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
        examples.append(ExampleFile(
            name=meta["name"],
            filename=f.name,
            description=meta["description"]
        ))
    
    logger.info(f"Found {len(examples)} example files in {examples_dir}")
    return examples


@router.get("/examples/{filename}")
async def get_example_file(filename: str):
    """Serve an example audio file."""
    # Security: only allow .wav files and prevent path traversal
    if not filename.endswith(".wav") or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    examples_dir = get_examples_dir()
    filepath = examples_dir / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Example file not found")
    
    return FileResponse(
        path=filepath,
        media_type="audio/wav",
        filename=filename
    )


@router.post("/examples/{filename}/analyze", response_model=AnalysisResponse)
async def analyze_example(filename: str):
    """Analyze an example file directly (saves client from downloading first)."""
    # Security: only allow .wav files and prevent path traversal
    if not filename.endswith(".wav") or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    examples_dir = get_examples_dir()
    filepath = examples_dir / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Example file not found")
    
    try:
        loop = asyncio.get_event_loop()
        
        # Load audio file
        audio_array, sample_rate = await loop.run_in_executor(
            None,
            lambda: librosa.load(str(filepath), sr=22050, mono=True, duration=MAX_AUDIO_DURATION_SECONDS)
        )
        
        # Process audio analysis
        detected_bpm, beat_times = await loop.run_in_executor(
            None,
            lambda: estimate_bpm_and_beats(audio_array, sample_rate)
        )
        
        ticks = ticks_from_beats(beat_times, subdiv=4)
        histogram = await loop.run_in_executor(
            None,
            lambda: groove_histogram(audio_array, sample_rate, ticks)
        )
        
        if histogram is None or not np.asarray(histogram).size or not np.any(histogram):
            histogram = (np.ones(16) / 16.0).tolist()
        else:
            histogram = histogram.tolist()
        
        suggested_scale, suggested_score = await loop.run_in_executor(
            None,
            lambda: detect_scale_from_audio(audio_array, sample_rate)
        )
        
        return AnalysisResponse(
            bpm=detected_bpm if detected_bpm else 120.0,
            scale=suggested_scale,
            scale_score=suggested_score,
            histogram=histogram
        )
    except Exception as e:
        logger.error(f"Error analyzing example file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze example: {str(e)}")
