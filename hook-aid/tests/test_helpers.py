import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pytest

from motif import detect_scale_from_audio
from ui_helpers import build_zip_name


@pytest.mark.parametrize(
    "upload, expected",
    [
        (None, "hooks.zip"),
        ("loop.wav", "hooks - loop.zip"),
        ("My Awesome Loop 01.mp3", "hooks - My-Awesome-Loop-01.zip"),
        ("   ???.wav", "hooks.zip"),
    ],
)
def test_build_zip_name(upload, expected):
    assert build_zip_name(upload) == expected


def test_detect_scale_from_audio_identifies_c_major():
    sr = 22050
    duration = 2.5
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # Triad: C4, E4, G4
    signal = (
        np.sin(2 * np.pi * 261.63 * t)
        + 0.8 * np.sin(2 * np.pi * 329.63 * t)
        + 0.6 * np.sin(2 * np.pi * 392.0 * t)
    )
    signal *= np.hanning(signal.size)
    scale, score = detect_scale_from_audio(signal.astype(np.float32), sr)
    assert scale == "C major"
    assert score >= 0.4


def test_detect_scale_from_audio_returns_none_on_noise():
    sr = 22050
    noise = np.random.RandomState(0).randn(sr)
    scale, score = detect_scale_from_audio(noise.astype(np.float32), sr)
    assert scale is None
    assert score < 0.3
