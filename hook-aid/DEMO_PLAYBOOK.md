# Hook Generator Aid – Demo Playbook

A quick run sheet for live walk-throughs.

## Before the Call
- Create/activate the project virtualenv: `python3 -m venv .venv && source .venv/bin/activate`.
- Install deps: `pip install -r requirements.txt`.
- Start the UI: `streamlit run app.py`.
- Preload the following example loops for fast access:
  - `examples/straight_120bpm.wav`
  - `examples/keys_eminor_100bpm.wav`
  - `examples/plucks_gmajor_110bpm.wav`
- Keep your DAW or audio player handy to audition the rendered hooks if asked.

## Demo Script (~5 minutes)
1. **Setup (30s)** – Show the running Streamlit app, mention the model generates five monophonic hooks.
2. **Upload a drum loop (60s)** – Use `straight_120bpm.wav`. Highlight the detected BPM, explain how the Groove push / Notes per bar controls change the feel.
3. **Scale suggestion (60s)** – Switch to `keys_eminor_100bpm.wav`. Call out the scale badge and the sidebar summary; tweak the scale to show manual override.
4. **Download (30s)** – Trigger the download, point out the auto-named archive (`hooks - keys_eminor_100bpm.zip`).
5. **Second example (60s)** – Load `plucks_gmajor_110bpm.wav` to show another suggestion and contrast register choices.
6. **Wrap-up (30s)** – Mention extensibility: new grooves in `examples/`, simple API surface in `motif.py`/`export.py`, and the chroma-based scale guess.

## FAQ Prompts
- *“How reliable is the scale detection?”* → Explain the confidence tiers (high/medium/low) and that purely percussive loops ask the user to choose.
- *“Can it output MIDI?”* → Point to `export.py` → `notes_to_midi_bytes` for future wiring.
- *“What about testing?”* → Mention `pytest` in this repo (see `tests/` for smoke checks on tempo/scale helpers).

Good luck with the session!
