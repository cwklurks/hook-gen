import librosa
import numpy as np


def load_mono(file, sr=22050):
    """Load audio file as mono with normalization."""
    y, sr = librosa.load(file, sr=sr, mono=True)
    y, _ = librosa.effects.trim(y, top_db=30)
    rms = np.sqrt(np.mean(y**2)) + 1e-8
    y = y * (0.1 / rms)
    return y, sr

def estimate_bpm_and_beats(y, sr, fast_mode=False):
    """
    Estimate BPM and beat positions from audio.
    
    Args:
        y: Audio signal (mono)
        sr: Sample rate
        fast_mode: If True, use faster synthetic beat generation (less accurate).
                   If False (default), use full beat tracking with shuffle/double-time detection.
    
    Returns:
        tempo: Detected tempo in BPM
        beat_times: Array of beat times in seconds
    """
    if fast_mode:
        # Fast mode: Ultra-fast BPM detection using onset autocorrelation
        # Generates synthetic beat times from detected tempo (backend approach)
        
        # Downsample for faster processing if sample rate is high
        if sr > 22050:
            factor = sr // 22050
            y = y[::factor]
            sr = sr // factor
        
        # Get onset strength (relatively fast)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=512)
        
        # Fast tempo estimation using autocorrelation (much faster than beat_track)
        # This avoids the expensive dynamic programming in beat_track
        try:
            tempo = librosa.feature.rhythm.tempo(onset_envelope=onset_env, sr=sr, hop_length=512)
            tempo = float(np.atleast_1d(tempo)[0])
        except AttributeError:
            # Older librosa versions
            tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr, hop_length=512)
            tempo = float(np.atleast_1d(tempo)[0])
        
        # Constrain tempo to reasonable range
        if tempo > 160:
            tempo /= 2.0
        elif tempo < 60:
            tempo *= 2.0
        
        tempo = max(60.0, min(180.0, tempo)) if tempo > 0 else 120.0
        
        # Generate synthetic beat times based on tempo (skip expensive beat tracking)
        duration = len(y) / sr
        beat_interval = 60.0 / tempo
        beat_times = np.arange(0, duration, beat_interval)
        
        return float(tempo), beat_times
    
    else:
        # Accurate mode: Full beat tracking with shuffle/double-time detection (hook-aid approach)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        
        # Get multiple tempo candidates for better accuracy
        tempo_candidates = np.atleast_1d(librosa.beat.tempo(onset_envelope=onset_env, sr=sr, aggregate=None))
        tempo_guess = 120.0
        
        if tempo_candidates.size:
            # Prefer tempos in the 60-160 BPM range
            for cand in np.sort(tempo_candidates):
                if 60.0 <= cand <= 160.0:
                    tempo_guess = float(cand)
                    break
            else:
                tempo_guess = float(tempo_candidates[0])

        tempo_guess = tempo_guess if tempo_guess > 0 else 120.0

        # Full beat tracking with the tempo guess
        tempo_track, beat_frames = librosa.beat.beat_track(
            onset_envelope=onset_env, 
            sr=sr, 
            start_bpm=tempo_guess, 
            trim=True
        )
        tempo_track = float(np.atleast_1d(tempo_track)[0]) if np.size(tempo_track) else tempo_guess
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)

        # CRITICAL: Shuffle and double-time detection
        # This is the key improvement from hook-aid version
        ratio = tempo_track / tempo_guess if tempo_guess else 1.0
        if beat_times.size >= 4:
            if 1.4 <= ratio <= 1.6:  # shuffle double-time tendency (3/2 factor)
                beat_times = beat_times[::2]
                tempo_track /= 1.5
            elif 1.9 <= ratio <= 2.1:  # strict double-time
                beat_times = beat_times[::2]
                tempo_track /= 2.0

        # Fall back to plain tracker if we got too few beats
        if beat_times.size < 2:
            tempo_track, beat_frames = librosa.beat.beat_track(y=y, sr=sr, trim=True)
            tempo_track = float(np.atleast_1d(tempo_track)[0]) if np.size(tempo_track) else tempo_guess
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)

        return float(tempo_track), beat_times

def ticks_from_beats(beat_times, subdiv=4):
    """
    Generate subdivision ticks from beat times.
    
    Args:
        beat_times: Array of beat times in seconds
        subdiv: Subdivisions per beat (4 = 16th notes)
    
    Returns:
        Array of tick times in seconds
    """
    # subdiv=4 → 16th notes
    if len(beat_times) < 2:
        return np.array([])
    tick_times = []
    for i in range(len(beat_times)-1):
        start, end = beat_times[i], beat_times[i+1]
        seg = np.linspace(start, end, subdiv, endpoint=False)
        tick_times.extend(seg.tolist())
    return np.array(tick_times)

def groove_histogram(y, sr, tick_times):
    """
    Generate a groove histogram from audio and tick times.
    
    Maps detected onsets to the nearest 16th-note position.
    
    Args:
        y: Audio signal
        sr: Sample rate
        tick_times: Array of tick times (typically from ticks_from_beats)
    
    Returns:
        16-element histogram normalized to sum to 1.0
    """
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    if tick_times.size == 0:
        return np.ones(16)/16
    hist = np.zeros(16)
    for t in onsets:
        idx = np.argmin(np.abs(tick_times - t))
        hist[idx % 16] += 1
    return hist / hist.sum() if hist.sum() > 0 else np.ones(16)/16

