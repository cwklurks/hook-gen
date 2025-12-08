import numpy as np, librosa

def load_mono(file, sr=22050):
    y, sr = librosa.load(file, sr=sr, mono=True)
    y, _ = librosa.effects.trim(y, top_db=30)
    rms = np.sqrt(np.mean(y**2)) + 1e-8
    y = y * (0.1 / rms)
    return y, sr

def estimate_bpm_and_beats(y, sr):
    """
    Simplified, faster BPM and beat detection.
    Single pass through beat_track instead of multiple tempo estimations.
    """
    # Single pass - let beat_track handle everything
    # This is much faster than computing onset_strength + tempo + beat_track separately
    tempo_result, beat_frames = librosa.beat.beat_track(y=y, sr=sr, trim=True)
    
    # Handle both old and new librosa return formats
    tempo = float(np.atleast_1d(tempo_result)[0]) if np.size(tempo_result) else 120.0
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    
    # Simple double-time correction if tempo seems too fast
    if tempo > 160 and beat_times.size >= 4:
        beat_times = beat_times[::2]
        tempo /= 2.0
    elif tempo < 60 and beat_times.size >= 2:
        # Interpolate beats if too slow
        tempo *= 2.0
    
    return float(tempo) if tempo > 0 else 120.0, beat_times

def ticks_from_beats(beat_times, subdiv=4):
    # subdiv=4 → 16th notes
    if len(beat_times) < 2: return np.array([])
    tick_times = []
    for i in range(len(beat_times)-1):
        start, end = beat_times[i], beat_times[i+1]
        seg = np.linspace(start, end, subdiv, endpoint=False)
        tick_times.extend(seg.tolist())
    return np.array(tick_times)

def groove_histogram(y, sr, tick_times):
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    if tick_times.size == 0: return np.ones(16)/16
    hist = np.zeros(16)
    for t in onsets:
        idx = np.argmin(np.abs(tick_times - t))
        hist[idx % 16] += 1
    return hist / hist.sum() if hist.sum() > 0 else np.ones(16)/16
