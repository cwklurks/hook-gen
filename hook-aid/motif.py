import numpy as np
import librosa

# Interval patterns are defined relative to the root and reused for any key.
SCALE_PATTERNS = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],  # natural minor
}

# Ordered to give users a practical mix of sharp and flat keys.
SCALE_ROOTS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# Map enharmonic spellings to semitone offsets from C.
NOTE_TO_SEMITONE = {
    "C": 0,
    "C#": 1, "Db": 1,
    "D": 2,
    "D#": 3, "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6, "Gb": 6,
    "G": 7,
    "G#": 8, "Ab": 8,
    "A": 9,
    "A#": 10, "Bb": 10,
    "B": 11,
}

DEFAULT_SCALE = "C minor"


def _build_scale_templates():
    templates = {}
    for root in SCALE_ROOTS:
        root_offset = NOTE_TO_SEMITONE[root]
        for quality, pattern in SCALE_PATTERNS.items():
            vec = np.zeros(12, dtype=float)
            for degree in pattern:
                vec[(root_offset + degree) % 12] = 1.0
            templates[f"{root} {quality}"] = vec / (np.linalg.norm(vec) + 1e-9)
    return templates


SCALE_TEMPLATES = _build_scale_templates()


def list_available_scales():
    """Return the scales the app can generate, keeping UI and pitch logic in sync."""
    return [f"{root} {quality}" for root in SCALE_ROOTS for quality in ("major", "minor")]


def _parse_scale(scale: str):
    """Normalize the scale string and return (root, quality, intervals)."""
    if not scale:
        scale = DEFAULT_SCALE
    parts = scale.strip().split()
    if not parts:
        return _parse_scale(DEFAULT_SCALE)
    if len(parts) < 2:
        root, quality = parts[0], "minor"
    else:
        root, quality = parts[0], parts[1]

    root = root[0].upper() + root[1:] if len(root) > 1 else root.upper()
    quality = quality.lower()

    if root not in NOTE_TO_SEMITONE:
        root = DEFAULT_SCALE.split()[0]
    if quality not in SCALE_PATTERNS:
        quality = DEFAULT_SCALE.split()[1]

    return root, quality, SCALE_PATTERNS[quality]

def sample_rhythm(hist16, density=7, syncopation=0.5, seed=0):
    rng = np.random.default_rng(seed)
    weights = hist16.copy()
    off = np.array([1,3,5,7,9,11,13,15])
    weights[off] += syncopation * weights.mean()
    weights = weights / weights.sum()
    onsets = sorted(rng.choice(16, size=min(density,16), replace=False, p=weights))
    durs = [1 + int(rng.random() < 0.25) for _ in onsets]  # 16ths, sometimes 8ths
    return list(zip(onsets, durs))

def midi_mapper(scale: str, base_octave: int = 4):
    root, _, degrees = _parse_scale(scale)
    root_midi = base_octave * 12 + NOTE_TO_SEMITONE[root]

    def fn(step_idx):
        octave = step_idx // len(degrees)
        deg = degrees[step_idx % len(degrees)]
        return root_midi + 12 * octave + deg

    return fn


def _fit_to_register(pitch: int, register):
    while pitch < register[0]:
        pitch += 12
    while pitch > register[1]:
        pitch -= 12
    return pitch


def assign_pitches(events, scale="C minor", register=(55,76), step_prob=0.8, max_leap=4, seed=0):
    rng = np.random.default_rng(seed)
    _, _, degrees = _parse_scale(scale)
    to_midi = midi_mapper(scale)
    idx = rng.integers(0, len(degrees))
    notes = []
    for onset, dur in events:
        if rng.random() < step_prob:
            idx += rng.choice([-1,1])
        else:
            idx += rng.integers(-max_leap, max_leap+1)
        idx = max(0, idx)
        pitch = _fit_to_register(to_midi(idx), register)
        notes.append((int(onset), int(dur), int(pitch)))
    if notes:
        o, d, _ = notes[-1]
        tonic = _fit_to_register(to_midi(0), register)
        notes[-1] = (int(o), int(d), int(tonic))  # resolve to tonic
    return notes


def detect_scale_from_audio(y, sr):
    """Return (scale, score) using a chroma template match; None if inconclusive."""
    if y is None or sr is None:
        return None, 0.0

    y = np.asarray(y)
    if y.size == 0 or not np.any(np.abs(y)):
        return None, 0.0

    harmonic, _ = librosa.effects.hpss(y)
    source = harmonic if np.any(np.abs(harmonic)) else y
    chroma = librosa.feature.chroma_cqt(y=source, sr=sr)
    if chroma.size == 0:
        return None, 0.0

    chroma_vector = chroma.mean(axis=1)
    if not np.any(chroma_vector):
        return None, 0.0

    chroma_norm = chroma_vector / (np.linalg.norm(chroma_vector) + 1e-9)
    best_scale = None
    best_score = -1.0
    second_score = -1.0

    for scale_name, template in SCALE_TEMPLATES.items():
        score = float(np.dot(chroma_norm, template))
        if score > best_score:
            second_score = best_score
            best_score = score
            best_scale = scale_name
        elif score > second_score:
            second_score = score

    if best_score < 0.25 or (second_score >= 0 and best_score - second_score < 0.08):
        return None, float(best_score)

    return best_scale, float(best_score)
