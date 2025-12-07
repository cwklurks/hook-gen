# Hook‑Gen Speaker Notes (12–15 minutes)

Speaker notes styled as a narrative script you can deliver in roughly 12–15 minutes. Adjust pacing depending on how deep you want to go into each subsystem.

## 1) Kick‑off: Why Hook‑Gen?
“We built Hook‑Gen to turn any groove into five melodic hooks that lock to the loop’s feel and key. Think of it as a fast ‘musical ideation engine’ for beatmakers and demo sprints.”

- Motivations: accelerate ideation over drum/percussion stems, keep musical decisions explainable, and stay CPU‑light so it runs anywhere without a GPU or big checkpoints.
- Scope: algorithmic generator + Streamlit UI. No training loop required; musicality comes from tempo/groove analysis and scale‑aware pitch sampling.

## 2) Baseline Capabilities & Repo Overview
- Surfaces:
  - Streamlit app for uploads, controls, preview, and zips: `hook-aid/app.py`.
- Core modules:
  - Rhythm analysis and groove histogram: `hook-aid/rhythm.py`.
  - Monophonic motif and pitch logic: `hook-aid/motif.py`.
  - Audio/MIDI export helpers: `hook-aid/export.py`.
  - UI utilities (download naming): `hook-aid/ui_helpers.py`.
- Artefacts:
  - Five per‑hook WAVs + a combined mix in a single zip named after the upload (e.g., “hooks - straight_120bpm.zip”).
  - Optional MIDI byte generation supported in code, not yet wired in the UI.
- Layout highlights:
  - Examples for rehearsals and demos: `hook-aid/examples/`.
  - A short run‑of‑show: `hook-aid/DEMO_PLAYBOOK.md`.
  - Smoke tests for scale detection and filename safety: `hook-aid/tests/test_helpers.py`.

## 3) Input Strategy & Provenance Posture
- Inputs: 1‑track loop (WAV or MP3). The app loads to mono at 22.05 kHz and analyzes tempo + groove + key suggestion (cached per upload).
- Guidance for demos: procedurally generated example loops cover straight, shuffle, halftime, four‑on‑the‑floor, and pitched material to demo edge cases.
- Provenance detail:
  - No training corpus; generation is deterministic per seed and parameters.
  - Download names sanitize the original filename to avoid unsafe paths.
  - Cached per‑upload analysis keeps repeated runs consistent and fast.

## 4) Signal Conditioning & Groove Extraction
- Load & prepare:
  - Streamlit path: `librosa.load` to 22.05 kHz mono; analysis cached via `st.cache_data`.
  - A utility exists for RMS‑normalised mono with silence trim (used in library contexts).
- Tempo + beats:
  - Onset envelope → initial tempo candidates → robust beat tracking with a seeded guess.
  - Double‑time/shuffle guards reduce common BPM confusions by folding every other beat when ratios suggest 3/2 or 2x.
- Tick grid + groove:
  - Convert beats to 16th‑note tick times.
  - Bin detected onsets against the tick grid to form a 16‑bin groove histogram, falling back to uniform when sparse.

## 5) Scale Detection & Musical Keying
- Detector:
  - HPSS to emphasize harmonic content; chroma‑CQT; average vector; cosine match against 24 template scales (12 roots × major/minor).
  - Ambiguity guard: returns None if best vs second‑best gap < 0.08 or best < 0.25, prompting manual selection.
- UX:
  - Confidence badge tiers: ≥0.6 “High”, ≥0.4 “Medium”, else “Low”; percussive loops nudge for manual keying.
  - Suggested scale preselects the UI dropdown if confident; otherwise defaults to “C minor”.
- Testability:
  - A synthetic C‑major triad test asserts correct detection; wideband noise asserts “None” with low score.

## 6) Rhythm Sampling & Pitch Assignment
- Rhythm from feel:
  - Start with the 16‑bin histogram; add “groove push” to weight off‑beats; sample unique onsets at 16th resolution; assign durations as 16ths with occasional 8ths.
  - User controls “Notes per bar” and “Groove push” to move from sparse/on‑grid to busy/syncopated.
- Pitch logic:
  - Random walk within the scale: mostly stepwise movement with occasional leaps (configurable); register‑bound to keep notes where you expect.
  - Resolve to tonic on the last note for musical closure.
- Registers:
  - Three presets mapped to MIDI ranges: low (48–69), mid (55–76), high (62–84).

## 7) Generation Loop & Determinism
- Seed strategy:
  - Session state seed increments on “Regenerate hooks” to produce a new rhythm/pitch set while keeping settings intact.
- Batch generation:
  - Five independent hooks per pass (varying seeds); immediate combined preview in‑browser; per‑hook WAVs and a mixdown are written to a zip buffer.
- Audio render:
  - Lightweight sine synth with short attack/release envelopes; per‑hook audio summed and normalised for the combined preview.

## 8) Inference Surfaces & UX
- Streamlit App:
  - Upload, see detected BPM + scale suggestion, adjust controls, preview, and download with one click.
  - Sidebar summarizes filename, sanitized download name, detected BPM, and suggested scale + confidence.
- Export surfaces (library API):
  - WAV per hook via `notes_to_wav_bytes`.
  - Combined WAV via `hooks_to_wav_bytes`.
  - MIDI bytes for a single hook and multitrack MIDI file writer (ready for a UI toggle in future).
- Scale catalog:
  - Programmatically derived list ensures UI and pitch mapping always stay in sync.

## 9) Deployment & Operational Notes
- Local dev:
  - Python 3.10+, `pip install -r hook-aid/requirements.txt`, launch with `streamlit run hook-aid/app.py`. Dependencies are CPU‑only (librosa, streamlit, mido).
- Containers/spaces:
  - No system codecs beyond what soundfile/librosa require; typical Debian libs suffice. Streamlit caches analysis by upload for snappy UX.
- Demo prep:
  - Use the curated `examples/` to cover straight, swung, halftime, and pitched cases; follow `hook-aid/DEMO_PLAYBOOK.md` for a 5‑minute version.

## 10) Reproducibility & Audit Trail
- Determinism knobs:
  - Seeded numpy RNG for both rhythm and pitch; same input + same controls + same seed ⇒ identical hooks.
- Download naming:
  - Sanitized, stable zip names to make assets traceable to inputs; verified in tests.
- Caching:
  - Per‑upload analysis memoization avoids recomputing tempo/chroma while iterating controls, keeping latency predictable.

## 11) Known Limitations & Roadmap Talking Points
- Quantization: 16th‑note grid by design; future: triplet grids, adaptive swing, or learned micro‑timing per style.
- Timbre: simple sine synth in preview; in‑DAW context you’ll replace with instruments. Roadmap: UI‑level MIDI export toggle using `notes_to_midi_bytes`.
- Key detection: chroma template match is explainable but not robust to heavy modal interchange. Roadmap: windowed voting, scale duration penalties, or a lightweight key classifier.
- Melody model: step/leap random walk is intentionally simple. Roadmap: style presets, contour constraints, cadence patterns, and optional learned embedding to bias pitch moves while retaining explainability.
- Tempo: double‑time/shuffle heuristics reduce drift but aren’t foolproof for complex polyrhythms. Roadmap: downbeat tracking and meter inference.

## 12) How to Extend
- Add a scale or mode:
  - Extend `SCALE_PATTERNS`; templates propagate everywhere; UI picks up new entries via `list_available_scales`.
- Change rhythmic character:
  - Modify off‑beat weighting or duration logic in `sample_rhythm`; add triplet bins by changing `subdiv` and histogram logic.
- New registers or instrument programs:
  - Tweak register map in app or expose a selector; for MIDI, set program/channel in export.
- Wire MIDI to UI:
  - Add a Streamlit checkbox and call `notes_to_midi_bytes` per hook; offer a combined multitrack `.mid` using `write_multi_track`.
- CI smoke:
  - Keep pytest for key heuristics; add a tempo regression test by synthesizing on‑grid onset trains and asserting BPM/beat counts.

---

## Live Demo Walkthrough (3–5 minutes within the talk)
- Start the app with `streamlit run hook-aid/app.py`.
- Upload `hook-aid/examples/straight_120bpm.wav`. Call out detected BPM, tweak Notes per bar and Groove push, click “Regenerate” to show variation without re‑uploading.
- Upload `hook-aid/examples/keys_eminor_100bpm.wav`. Show the scale badge + confidence and the sidebar summary; override the scale to demonstrate manual control.
- Download the zip; point at the sanitized filename printed in the sidebar (e.g., “hooks - keys_eminor_100bpm.zip”).
- Close with `hook-aid/examples/plucks_gmajor_110bpm.wav` to contrast registers (low vs high).

## Closing Soundbite
“Hook‑Gen is a focused, explainable generator: it reads your groove, proposes a key, and gives you five usable hooks immediately. It’s production‑light, deterministic when you need it, and extensible—great scaffolding if we later bias it with learned style embeddings or wire MIDI straight into a DAW.”

