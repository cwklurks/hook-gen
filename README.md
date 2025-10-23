# Hook Generator Aid

[![Streamlit](https://img.shields.io/badge/Streamlit-ready-ff4b4b.svg)](https://streamlit.io/) [![Python](https://img.shields.io/badge/python-3.10+-3776ab.svg)](https://www.python.org/)

A Streamlit front-end around the hook-gen model: drop in a loop, get five melodic hooks that line up with the groove and the key. 🎶 Built for quick ideation sessions, perfect for tomorrow's demo.

---

## Table of Contents
- [Highlights](#highlights)
- [Live Demo Flow](#live-demo-flow)
- [Quick Start](#quick-start)
- [Controls at a Glance](#controls-at-a-glance)
- [Scale Detection](#scale-detection)
- [Bundled Example Loops](#bundled-example-loops)
- [Download Contents](#download-contents)
- [Testing](#testing)
- [Project Layout](#project-layout)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

## Highlights
- 🎛️ Groove-aware rhythm sampling driven by the uploaded loop's onset histogram.
- 🎯 Optional scale suggestion through chroma analysis, with a confidence badge and sidebar read-out.
- 🎚️ Three quick voicing registers (`low`, `mid`, `high`) so you can revoice hooks without tweaking code.
- 📦 Download bundle named after the uploaded file, ready to drag-drop into a DAW session.
- 🎬 Demo playbook plus synthetic audio assets so you can rehearse offline.
- ♻️ One-click regenerate button to audition fresh rhythmic and pitch variations without re-uploading.
- 🔉 Inline audio preview lets you hear the combined hook mix before committing to a download.

## Live Demo Flow
If you're showing this project, open `DEMO_PLAYBOOK.md` for a timed script. The short version:
1. 🎧 Fire up the app with `streamlit run app.py`.
2. 🥁 Use `examples/straight_120bpm.wav` to introduce the BPM detection and groove controls.
3. 🎯 Switch to a pitched loop such as `examples/keys_eminor_100bpm.wav` to highlight the scale badge and override flow.
4. 📦 Download the archive and mention the auto-named ZIP.
5. 🎸 Close with `examples/plucks_gmajor_110bpm.wav` to showcase how register swaps change the character.

## Quick Start
⚡ Ready in four commands:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
The app launches at `http://localhost:8501`.

## Controls at a Glance
🎚️ Dial in the feel with these widgets:

| Control | Default | What it does |
| --- | --- | --- |
| **Notes per bar** | 7 | Sets how many 16th-note events the rhythm sampler pulls from the groove histogram. |
| **Groove push** | 0.5 | Nudges hits toward off-beats; 0 locks to the grid, 1 leans into syncopation. |
| **Pitch range** | `mid` | Keeps notes within a register (low/mid/high) so hooks sit where you expect. |
| **BPM** | Detected value | Appears after upload; tweak it if the automatic tempo guess feels wrong. |
| **Scale** | Suggested or C minor | Uses chroma detection to pre-select a key; always editable. |

Each slider includes inline help text. A summary of file name, BPM, and scale confidence also lives in the sidebar.

## Scale Detection
- 🎼 Uses `librosa` chroma templates for every major/minor key.
- ✅ Confidence ≥ 0.6 → green badge; ≥ 0.4 → amber; anything lower prompts caution.
- 🥁 Purely percussive loops fall back to "pick a scale manually" so you never get a misleading default.

## Bundled Example Loops
All loops live in `examples/` and are procedurally generated. 🎵

| File | Style & Use Case | Length |
| --- | --- | --- |
| `groove_100bpm.wav` | 1-bar teaser, straight funk pocket | ~2.4s |
| `groove_100bpm_long.wav` | Extended version for longer auditions | ~38.4s |
| `shuffle_92bpm.wav` | Swung hats to stress-test shuffle handling | ~2.6s |
| `straight_120bpm.wav` | Bread-and-butter pop/rock beat | ~24.0s |
| `reggaeton_96bpm.wav` | Dembow kick pattern with off-beat snares | ~30.0s |
| `halftime_70bpm.wav` | Sparse halftime groove plus ghost notes | ~41.1s |
| `brokenbeat_128bpm.wav` | Busy 16th hats with syncopated kicks | ~22.5s |
| `fouronthefloor_124bpm.wav` | House-style four-on-the-floor drive | ~23.2s |
| `keys_eminor_100bpm.wav` | Pad chords with clear E minor tonality | ~28.8s |
| `bass_cminor_90bpm.wav` | Synth bass riff outlining C minor | ~32.0s |
| `plucks_gmajor_110bpm.wav` | Plucked pattern outlining G major | ~26.2s |

## Download Contents
Every render produces a zip named `hooks - <uploaded-file>.zip` containing:
- 🎶 `hook_1.wav` … `hook_5.wav`
- 🎧 `hooks_combined.wav`
You can re-export or extend to MIDI by reusing the helpers in `export.py`.

## Testing
Smoke tests live under `tests/`. ✅
```bash
cd hook-aid
python3 -m pip install pytest  # one-time
python3 -m pytest tests
```
The suite exercises scale detection on synthetic audio and validates the download filename helper.

## Project Layout
```
hook-aid/
 ├─ app.py              # Streamlit UI
 ├─ motif.py            # Rhythm + pitch generation utilities
 ├─ rhythm.py           # Tempo detection and groove histogram helpers
 ├─ export.py           # Audio (and MIDI-ready) export helpers
 ├─ examples/           # Drum & melodic loops for demoing
 ├─ ui_helpers.py       # Presentation helpers (download naming, etc.)
 ├─ tests/              # Pytest smoke checks
 ├─ DEMO_PLAYBOOK.md    # Run-of-show cheat sheet
 └─ requirements.txt    # Streamlit + audio stack dependencies
```

## Roadmap
- 🎹 Optional MIDI export in the UI (already available in `export.py`).
- 🎛️ Presets for "chill", "busy", or "syncopated" settings to speed up live tweaking.
- 🧠 Save favorite slider combinations as recallable presets.

## Contributing
Issues and pull requests are welcome. 🤝 If you introduce new example loops, include a short description or clip so others can regression-test by ear.
