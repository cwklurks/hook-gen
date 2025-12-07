from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal
import io
import librosa
import numpy as np
from math import isclose
import logging
import asyncio
import os

logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB default
AUDIO_PROCESSING_TIMEOUT_SECONDS = 60  # 60 seconds timeout for audio processing

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

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_audio(file: UploadFile = File(...)):
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
            loop = asyncio.get_event_loop()
            audio_array, sample_rate = await loop.run_in_executor(
                None,
                lambda: librosa.load(buffer, sr=22050, mono=True)
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
