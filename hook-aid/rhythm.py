import numpy as np, librosa

def load_mono(file, sr=22050):
    y, sr = librosa.load(file, sr=sr, mono=True)
    y, _ = librosa.effects.trim(y, top_db=30)
    rms = np.sqrt(np.mean(y**2)) + 1e-8
    y = y * (0.1 / rms)
    return y, sr

def estimate_bpm_and_beats(y, sr):
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo_candidates = np.atleast_1d(librosa.beat.tempo(onset_envelope=onset_env, sr=sr, aggregate=None))
    tempo_guess = 120.0
    if tempo_candidates.size:
        for cand in np.sort(tempo_candidates):
            if 60.0 <= cand <= 160.0:
                tempo_guess = float(cand)
                break
        else:
            tempo_guess = float(tempo_candidates[0])

    tempo_guess = tempo_guess if tempo_guess > 0 else 120.0

    tempo_track, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, start_bpm=tempo_guess, trim=True)
    tempo_track = float(np.atleast_1d(tempo_track)[0]) if np.size(tempo_track) else tempo_guess
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    ratio = tempo_track / tempo_guess if tempo_guess else 1.0
    if beat_times.size >= 4:
        if 1.4 <= ratio <= 1.6:  # shuffle double-time tendency (3/2 factor)
            beat_times = beat_times[::2]
            tempo_track /= 1.5
        elif 1.9 <= ratio <= 2.1:  # strict double-time
            beat_times = beat_times[::2]
            tempo_track /= 2.0

    if beat_times.size < 2:  # fall back to the plain tracker if needed
        tempo_track, beat_frames = librosa.beat.beat_track(y=y, sr=sr, trim=True)
        tempo_track = float(np.atleast_1d(tempo_track)[0]) if np.size(tempo_track) else tempo_guess
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    return float(tempo_track), beat_times

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
