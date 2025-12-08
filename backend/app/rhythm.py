import numpy as np, librosa

def load_mono(file, sr=22050):
    y, sr = librosa.load(file, sr=sr, mono=True)
    y, _ = librosa.effects.trim(y, top_db=30)
    rms = np.sqrt(np.mean(y**2)) + 1e-8
    y = y * (0.1 / rms)
    return y, sr

def estimate_bpm_and_beats(y, sr):
    """
    Ultra-fast BPM detection using onset autocorrelation.
    Generates synthetic beat times from detected tempo.
    """
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
