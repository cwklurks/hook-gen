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


# Krumhansl-Schmuckler Key Profiles
# Major: [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
# Minor: [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]

KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

def _build_scale_templates():
    templates = {}
    for root in SCALE_ROOTS:
        root_offset = NOTE_TO_SEMITONE[root]
        
        # Major
        vec_major = np.roll(KS_MAJOR, root_offset)
        templates[f"{root} major"] = vec_major / (np.linalg.norm(vec_major) + 1e-9)
        
        # Minor
        vec_minor = np.roll(KS_MINOR, root_offset)
        templates[f"{root} minor"] = vec_minor / (np.linalg.norm(vec_minor) + 1e-9)
            
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
    
    # Sharpen the weights to lock to the groove more tightly if syncopation is low
    if syncopation < 0.3:
        weights = weights ** 2
        
    off = np.array([1,3,5,7,9,11,13,15])
    weights[off] += syncopation * weights.mean()
    
    # Normalize
    if weights.sum() > 0:
        weights = weights / weights.sum()
    else:
        weights = np.ones(16) / 16.0
        
    onsets = sorted(rng.choice(16, size=min(density,16), replace=False, p=weights))
    durs = [1 + int(rng.random() < 0.25) for _ in onsets]  # 16ths, sometimes 8ths
    return list(zip(onsets, durs))


def midi_mapper(scale: str, base_octave: int = 4):
    """Create a function that maps scale degree indices to MIDI pitches."""
    root, _, degrees = _parse_scale(scale)
    root_midi = base_octave * 12 + NOTE_TO_SEMITONE[root]

    def fn(step_idx):
        octave = step_idx // len(degrees)
        deg = degrees[step_idx % len(degrees)]
        return root_midi + 12 * octave + deg

    return fn


def _fit_to_register(pitch: int, register):
    """Shift pitch up or down by octaves to fit within the register range."""
    while pitch < register[0]:
        pitch += 12
    while pitch > register[1]:
        pitch -= 12
    return pitch


def generate_motif(histogram, scale="C minor", register=(55, 76), density=7, syncopation=0.5, seed=0):
    """Generate a single bar motif with rhythm from histogram and pitches from scale."""
    rng = np.random.default_rng(seed)
    
    # Sample rhythm from the groove histogram
    events = sample_rhythm(histogram, density, syncopation, seed)
    
    # Assign pitches
    _, _, degrees = _parse_scale(scale)
    to_midi = midi_mapper(scale)
    idx = rng.integers(0, len(degrees))
    
    notes = []
    step_prob = 0.8
    max_leap = 4
    
    for onset, dur in events:
        if rng.random() < step_prob:
            idx += rng.choice([-1, 1])
        else:
            idx += rng.integers(-max_leap, max_leap + 1)
        idx = max(0, idx)
        pitch = _fit_to_register(to_midi(idx), register)
        notes.append({
            "start": int(onset),
            "duration": int(dur),
            "pitch": int(pitch),
            "velocity": int(80 + rng.integers(-10, 10))
        })
    
    return notes


def vary_motif(motif, scale="C minor", register=(55, 76), seed=0):
    """Create a variation of the motif by slightly altering pitches and rhythms."""
    rng = np.random.default_rng(seed)
    _, _, degrees = _parse_scale(scale)
    to_midi = midi_mapper(scale)
    
    varied = []
    for note in motif:
        new_note = note.copy()
        
        # Randomly vary pitch by a step or two
        if rng.random() < 0.4:
            # Find current scale degree approximately
            current_pitch = note["pitch"]
            # Shift by 1-2 scale degrees
            shift = rng.choice([-2, -1, 1, 2])
            # Calculate new pitch
            new_pitch = current_pitch + shift
            new_pitch = _fit_to_register(new_pitch, register)
            new_note["pitch"] = int(new_pitch)
        
        # Occasionally shift timing slightly
        if rng.random() < 0.2:
            new_note["start"] = max(0, min(15, note["start"] + rng.choice([-1, 1])))
        
        # Vary velocity
        new_note["velocity"] = int(max(60, min(127, note["velocity"] + rng.integers(-15, 15))))
        
        varied.append(new_note)
    
    return varied

def generate_structured_hook(histogram, scale="C minor", register=(55,76), density=7, syncopation=0.5, seed=0):
    """Generate a 4-bar hook with A-A-B-A structure."""
    
    # Generate Motif A (Bar 1)
    motif_a = generate_motif(histogram, scale, register, density, syncopation, seed)
    
    # Generate Motif B (Bar 3 - Variation)
    motif_b = vary_motif(motif_a, scale, register, seed + 1)
    
    # Assemble A-A-B-A
    full_hook = []
    
    # Bar 1: A
    for note in motif_a:
        full_hook.append(note.copy())
        
    # Bar 2: A (maybe slight variation?)
    for note in motif_a:
        n = note.copy()
        n["start"] += 16 # Shift to 2nd bar
        full_hook.append(n)
        
    # Bar 3: B
    for note in motif_b:
        n = note.copy()
        n["start"] += 32 # Shift to 3rd bar
        full_hook.append(n)
        
    # Bar 4: A (Resolution)
    for note in motif_a:
        n = note.copy()
        n["start"] += 48 # Shift to 4th bar
        full_hook.append(n)
        
    # Musical Constraints: End on Tonic
    if full_hook:
        to_midi = midi_mapper(scale)
        tonic = _fit_to_register(to_midi(0), register)
        
        # 1. Set last note to Tonic
        last_note = full_hook[-1]
        last_note["pitch"] = tonic
        
        # 2. Approach from Leading Tone (or Dominant)
        if len(full_hook) > 1:
            penultimate = full_hook[-2]
            # Leading tone is index -1 (or 6 in major, 6/7 in minor depending on scale)
            # Let's just use the 7th degree of the scale pattern (index -1 in our arrays usually)
            # Actually, let's use the midi_mapper to find the note below the tonic
            
            # Find scale degree of tonic (0) -> -1 is leading tone
            leading_tone = _fit_to_register(to_midi(-1), register)
            
            # If leading tone is too far, try dominant (index 4)
            dominant = _fit_to_register(to_midi(4), register)
            
            # Choose leading tone if it's close to the penultimate note's current pitch, else dominant
            if abs(penultimate["pitch"] - leading_tone) < abs(penultimate["pitch"] - dominant):
                penultimate["pitch"] = leading_tone
            else:
                penultimate["pitch"] = dominant
        
    return full_hook


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

    # Return best guess regardless of low confidence (let the UI show the score)
    return best_scale, float(best_score)
