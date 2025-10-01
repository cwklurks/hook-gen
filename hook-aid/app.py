import io
import zipfile
from typing import Optional

import librosa
import numpy as np
import streamlit as st

from rhythm import estimate_bpm_and_beats, ticks_from_beats, groove_histogram
from motif import sample_rhythm, assign_pitches, list_available_scales, detect_scale_from_audio
from export import notes_to_wav_bytes, hooks_to_wav_bytes
from ui_helpers import build_zip_name


st.set_page_config(page_title="Hook Generator Aid", layout="centered")
st.title("Hook Generator Aid")
st.caption("Upload a drum loop → generate five groove-locked monophonic hooks")


def _confidence_badge(scale: Optional[str], score: float) -> None:
    if not scale:
        st.info("Scale detection: loop sounded mostly percussive, so pick a scale manually.")
        return

    if score >= 0.6:
        tone = "success"
        note = "High confidence"
    elif score >= 0.4:
        tone = "warning"
        note = "Medium confidence"
    else:
        tone = "info"
        note = "Low confidence"

    msg = f"{note}: suggested scale **{scale}** (confidence {score:.2f})."
    getattr(st, tone)(msg)


file = st.file_uploader("Upload WAV/MP3", type=["wav", "mp3"])

scale_options = list_available_scales()
default_scale = "C minor"
scale_index = scale_options.index(default_scale) if default_scale in scale_options else 0

suggested_scale = None
suggested_score = 0.0
uploaded_name = None
audio_array = None
sample_rate = None
histogram = None
detected_bpm = None

notes_help = "Lower values give sparse hooks, higher values pack in more notes each bar."
density = st.slider("Notes per bar", 4, 12, 7, help=notes_help)

sync_help = "0 keeps hits on the grid; 1 pushes accents to the off-beats for a funkier feel."
sync = st.slider("Groove push", 0.0, 1.0, 0.5, 0.1, help=sync_help)

register_help = "Low hugs the lower octave, mid sits around middle C, high jumps up an octave."
register = st.select_slider("Pitch range", options=["low", "mid", "high"], value="mid", help=register_help)

if file:
    uploaded_name = file.name
    file.seek(0)
    audio_bytes = file.read()
    audio_array, sample_rate = librosa.load(io.BytesIO(audio_bytes), sr=22050, mono=True)

    detected_bpm, beat_times = estimate_bpm_and_beats(audio_array, sample_rate)
    ticks = ticks_from_beats(beat_times, subdiv=4)
    histogram = groove_histogram(audio_array, sample_rate, ticks)
    if histogram is None or not np.any(histogram):
        histogram = np.ones(16) / 16.0

    suggested_scale, suggested_score = detect_scale_from_audio(audio_array, sample_rate)
    if suggested_scale and suggested_scale in scale_options:
        scale_index = scale_options.index(suggested_scale)

scale = st.selectbox(
    "Scale",
    scale_options,
    index=scale_index,
    help="Choose the key for the generated hooks. Override the suggestion if it sounds off.",
)

sidebar = st.sidebar
sidebar.header("Loop Summary")
if uploaded_name:
    sidebar.markdown(f"**File:** {uploaded_name}")
    sidebar.markdown(f"**Download:** `{build_zip_name(uploaded_name)}`")
    if detected_bpm:
        sidebar.markdown(f"**Detected BPM:** {detected_bpm:.1f}")
    if suggested_scale:
        sidebar.markdown(f"**Suggested scale:** {suggested_scale} ({suggested_score:.2f})")
    else:
        sidebar.markdown("**Suggested scale:** (manual selection)")
else:
    sidebar.info("Upload a loop above to see session details.")

if file:
    _confidence_badge(suggested_scale, suggested_score)

if audio_array is not None:
    st.write(f"Detected BPM: **{detected_bpm:.1f}** (override with the slider if it feels wrong)")
    bpm = st.slider(
        "BPM",
        60,
        180,
        int(round(detected_bpm)),
        help="Use this to correct the tempo if the detector guesses wrong.",
    )

    reg_map = {"low": (48, 69), "mid": (55, 76), "high": (62, 84)}
    hooks = []
    for i in range(5):
        events = sample_rhythm(histogram, density=density, syncopation=sync, seed=i)
        notes = assign_pitches(events, scale=scale, register=reg_map[register], seed=i)
        hooks.append(notes)

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        for i, notes in enumerate(hooks, 1):
            wav_bytes = notes_to_wav_bytes(notes, bpm=bpm)
            zf.writestr(f"hook_{i}.wav", wav_bytes)
        zf.writestr("hooks_combined.wav", hooks_to_wav_bytes(hooks, bpm=bpm))

    download_name = build_zip_name(uploaded_name)
    st.download_button(
        "Download 5 hooks (ZIP)",
        data=zbuf.getvalue(),
        file_name=download_name,
        mime="application/zip",
    )
