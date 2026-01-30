#!/usr/bin/env python3
"""
Generate synthetic drum loop WAV files from genre groove histograms.

Synthesizes drum loops for each genre in GENRE_TEMPLATES using pure numpy
for drum voice synthesis (kick, snare, hi-hat). Output files use a
``_generated`` suffix to distinguish them from hand-crafted examples.

Usage:
  python generate_examples.py
  python generate_examples.py --output-dir /path/to/dir --n-bars 8
"""

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
from hookgen_core.genre import GENRE_TEMPLATES

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VELOCITY_THRESHOLD = 0.02
PEAK_NORMALIZE = 0.89
_RNG = np.random.default_rng(seed=42)

# Genre tag -> (BPM, filename stem)
_GENRE_META: dict[str, tuple[int, str]] = {
    "house_four_on_floor": (124, "house_four_on_floor_124bpm"),
    "reggaeton_dembow": (96, "reggaeton_dembow_96bpm"),
    "trap_halftime": (140, "trap_halftime_140bpm"),
    "dnb_breakbeat": (174, "dnb_breakbeat_174bpm"),
    "techno_driving": (130, "techno_driving_130bpm"),
}


# ---------------------------------------------------------------------------
# Drum voice synthesis
# ---------------------------------------------------------------------------


def synthesize_kick(sample_rate: int) -> np.ndarray:
    """Synthesize a single kick drum hit (0.15 s)."""
    duration = 0.15
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    # Frequency sweep 150 -> 40 Hz
    freq = 150.0 * np.exp(-6.0 * t / duration) + 40.0
    phase = np.cumsum(freq) / sample_rate
    body = np.sin(2.0 * np.pi * phase) * np.exp(-8.0 * t / duration)

    # Transient click
    click = _RNG.standard_normal(n_samples) * np.exp(-50.0 * t / duration) * 0.15

    result: np.ndarray = (body + click).astype(np.float32) * 0.7
    return result


def synthesize_snare(sample_rate: int) -> np.ndarray:
    """Synthesize a single snare hit (0.12 s)."""
    duration = 0.12
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    tone = np.sin(2.0 * np.pi * 200.0 * t) * np.exp(-12.0 * t / duration) * 0.4
    noise = _RNG.standard_normal(n_samples) * np.exp(-8.0 * t / duration) * 0.6

    result: np.ndarray = (tone + noise).astype(np.float32) * 0.5
    return result


def synthesize_hihat(sample_rate: int) -> np.ndarray:
    """Synthesize a single closed hi-hat hit (0.05 s)."""
    duration = 0.05
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    noise = _RNG.standard_normal(n_samples)
    envelope = np.exp(-40.0 * t / duration)

    result: np.ndarray = (noise * envelope).astype(np.float32) * 0.35
    return result


# ---------------------------------------------------------------------------
# Pattern conversion
# ---------------------------------------------------------------------------


def histogram_to_pattern(
    histogram: list[float],
) -> list[tuple[int, str, int]]:
    """Convert a 16-element groove histogram to a drum pattern.

    Returns a list of (position, voice, velocity) tuples where
    position is 0-15 (16th-note index), voice is one of
    ``"kick"``, ``"snare"``, ``"hihat"``, and velocity is 0-127.
    """
    h = np.array(histogram, dtype=float)

    # Zero values below threshold
    h[h < VELOCITY_THRESHOLD] = 0.0

    if h.max() == 0:
        return []

    # Normalize to [0.3, 1.0] range for non-zero entries
    h = h / h.max()
    h[h > 0] = 0.3 + 0.7 * h[h > 0]

    velocities = (h * 127).astype(int)

    kick_positions = {0, 8}
    snare_positions = {4, 12}

    pattern: list[tuple[int, str, int]] = []
    for pos in range(16):
        vel = int(velocities[pos])
        if vel <= 0:
            continue
        if pos in kick_positions:
            pattern.append((pos, "kick", vel))
        elif pos in snare_positions:
            pattern.append((pos, "snare", vel))
        else:
            pattern.append((pos, "hihat", vel))

    return pattern


# ---------------------------------------------------------------------------
# Loop rendering
# ---------------------------------------------------------------------------


def render_drum_loop(
    pattern: list[tuple[int, str, int]],
    bpm: int,
    n_bars: int,
    sample_rate: int,
) -> np.ndarray:
    """Render a drum pattern into a multi-bar audio loop.

    Args:
        pattern: List of (position, voice, velocity) from histogram_to_pattern.
        bpm: Tempo in beats per minute.
        n_bars: Number of bars to render.
        sample_rate: Audio sample rate in Hz.

    Returns:
        Float32 mono audio array, peak-normalized.
    """
    # Pre-render single hits
    voices = {
        "kick": synthesize_kick(sample_rate),
        "snare": synthesize_snare(sample_rate),
        "hihat": synthesize_hihat(sample_rate),
    }

    # Duration of one 16th note in samples
    sixteenth_dur = 60.0 / bpm / 4.0
    sixteenth_samples = int(sixteenth_dur * sample_rate)

    total_steps = 16 * n_bars
    total_samples = sixteenth_samples * total_steps
    audio = np.zeros(total_samples, dtype=np.float64)

    for bar in range(n_bars):
        for pos, voice, vel in pattern:
            step = bar * 16 + pos
            start = step * sixteenth_samples
            hit = voices[voice].astype(np.float64) * (vel / 127.0)
            end = min(start + len(hit), total_samples)
            audio[start:end] += hit[: end - start]

    # Peak normalize
    peak = np.abs(audio).max()
    if peak > 0:
        audio = audio * (PEAK_NORMALIZE / peak)

    return audio.astype(np.float32)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic drum loop WAV files from genre groove histograms.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "examples",
        help="Output directory for generated WAV files (default: ../examples)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=44100,
        help="Sample rate in Hz (default: 44100)",
    )
    parser.add_argument(
        "--n-bars",
        type=int,
        default=4,
        help="Number of bars per loop (default: 4)",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating drum loops → {output_dir}")
    print(f"Sample rate: {args.sample_rate} Hz, Bars: {args.n_bars}")
    print(f"{'=' * 60}")

    for tag, (bpm, stem) in _GENRE_META.items():
        template = GENRE_TEMPLATES[tag]["template"]
        pattern = histogram_to_pattern(template)

        audio = render_drum_loop(pattern, bpm, args.n_bars, args.sample_rate)
        duration = len(audio) / args.sample_rate

        filename = f"{stem}_generated.wav"
        out_path = output_dir / filename
        sf.write(str(out_path), audio, args.sample_rate, subtype="FLOAT")

        print(f"  {filename:45s} {bpm:>3d} BPM  {duration:5.1f}s  {len(pattern):>2d} hits/bar")

    print(f"{'=' * 60}")
    print(f"Done. {len(_GENRE_META)} files written.")


if __name__ == "__main__":
    main()
