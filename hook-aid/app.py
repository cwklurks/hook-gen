import io, zipfile, streamlit as st, librosa
from rhythm import estimate_bpm_and_beats, ticks_from_beats, groove_histogram
from motif import sample_rhythm, assign_pitches
from export import notes_to_wav_bytes, hooks_to_wav_bytes

st.set_page_config(page_title="Hook Generator Aid (MVP)", layout="centered")
st.title("Hook Generator Aid (MVP)")
st.caption("Upload a drum loop → generate 5 groove-locked monophonic MIDI hooks")

file = st.file_uploader("Upload WAV/MP3", type=["wav","mp3"])
scale = st.selectbox("Scale", ["C minor","C major"])
density = st.slider("Note density (per bar)", 4, 12, 7)
sync = st.slider("Syncopation", 0.0, 1.0, 0.5, 0.1)
register = st.select_slider("Register (approx)", options=["low","mid","high"], value="mid")

if file:
    y, sr = librosa.load(io.BytesIO(file.read()), sr=22050, mono=True)
    tempo, beat_times = estimate_bpm_and_beats(y, sr)
    ticks = ticks_from_beats(beat_times, subdiv=4)
    hist = groove_histogram(y, sr, ticks)
    st.write(f"Detected BPM: **{tempo:.1f}** (override with slider if off)")
    tempo = st.slider("BPM", 60, 180, int(round(tempo)))

    reg_map = {"low": (48,69), "mid": (55,76), "high": (62,84)}
    hooks = []
    for i in range(5):
        events = sample_rhythm(hist, density=density, syncopation=sync, seed=i)
        notes  = assign_pitches(events, scale=scale, register=reg_map[register], seed=i)
        hooks.append(notes)

    # downloads
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        for i, notes in enumerate(hooks, 1):
            wav_bytes = notes_to_wav_bytes(notes, bpm=tempo)
            zf.writestr(f"hook_{i}.wav", wav_bytes)
        zf.writestr("hooks_combined.wav", hooks_to_wav_bytes(hooks, bpm=tempo))
    st.download_button("Download 5 hooks (ZIP)", data=zbuf.getvalue(), file_name="hooks.zip", mime="application/zip")
