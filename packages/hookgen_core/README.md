# HookGen Core

Shared library for musical hook generation and audio analysis.

## Features

- **Rhythm Analysis**: BPM detection, beat tracking, and groove pattern extraction
- **Motif Generation**: Musical hook creation with scale/key awareness
- **Audio Export**: MIDI and WAV file generation from note sequences
- **Key Detection**: Automatic musical key detection from audio

## Installation

```bash
pip install -e /path/to/packages/hookgen_core
```

## Usage

```python
from hookgen_core import (
    load_mono,
    estimate_bpm_and_beats,
    detect_scale_from_audio,
    generate_structured_hook,
    notes_to_midi_bytes,
)

# Load audio
audio, sr = load_mono("loop.wav")

# Analyze
bpm, beats = estimate_bpm_and_beats(audio, sr)
scale, score = detect_scale_from_audio(audio, sr)

# Generate hooks
hook = generate_structured_hook(histogram, scale=scale, density=7)
```

## Modules

- `rhythm`: Audio analysis and rhythm detection
- `motif`: Musical motif and hook generation
- `export`: MIDI and audio file export
- `ui_helpers`: UI utility functions
- `pkg_resources`: Minimal pkg_resources shim




