import numpy as np

SCALE_DEGREES = {
    "C major": [0,2,4,5,7,9,11],
    "C minor": [0,2,3,5,7,8,10]
}

def sample_rhythm(hist16, density=7, syncopation=0.5, seed=0):
    rng = np.random.default_rng(seed)
    weights = hist16.copy()
    off = np.array([1,3,5,7,9,11,13,15])
    weights[off] += syncopation * weights.mean()
    weights = weights / weights.sum()
    onsets = sorted(rng.choice(16, size=min(density,16), replace=False, p=weights))
    durs = [1 + int(rng.random() < 0.25) for _ in onsets]  # 16ths, sometimes 8ths
    return list(zip(onsets, durs))

def midi_mapper(root_midi=60, scale="C minor"):
    degrees = SCALE_DEGREES.get(scale, SCALE_DEGREES["C minor"])
    def fn(step_idx):
        octave = step_idx // len(degrees)
        deg = degrees[step_idx % len(degrees)]
        return root_midi + 12*octave + deg
    return fn

def assign_pitches(events, scale="C minor", register=(55,76), step_prob=0.8, max_leap=4, seed=0):
    rng = np.random.default_rng(seed)
    to_midi = midi_mapper(60 if "major" in scale else 57, scale)
    idx = rng.integers(0, 7)
    notes = []
    for onset, dur in events:
        if rng.random() < step_prob:
            idx += rng.choice([-1,1])
        else:
            idx += rng.integers(-max_leap, max_leap+1)
        idx = max(0, idx)
        pitch = to_midi(idx)
        while pitch < register[0]: pitch += 12
        while pitch > register[1]: pitch -= 12
        notes.append((onset, dur, pitch))
    if notes:
        o,d,_ = notes[-1]; notes[-1] = (o, d, to_midi(0))  # resolve to tonic
    return notes
