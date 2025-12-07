import io
import wave
from typing import Iterable, Tuple

import numpy as np
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo


DEFAULT_TICKS_PER_BEAT = 480
TIME_SIGNATURE = {
    "numerator": 4,
    "denominator": 4,
    "clocks_per_click": 24,
    "notated_32nd_notes_per_beat": 8,
}

Note = Tuple[int, int, int]


def _ticks_for_onset(onset: int, ticks_per_beat: int) -> int:
    return max(0, int(round(onset * ticks_per_beat / 4.0)))


def _ticks_for_duration(duration: int, ticks_per_beat: int) -> int:
    return max(1, int(round(duration * ticks_per_beat / 4.0)))


def _append_notes(track: MidiTrack, notes: Iterable[Note], *, channel: int, ticks_per_beat: int, velocity: int = 96) -> None:
    events = []
    for onset, dur, pitch in notes:
        start_tick = _ticks_for_onset(onset, ticks_per_beat)
        end_tick = start_tick + _ticks_for_duration(dur, ticks_per_beat)
        events.append((start_tick, "note_on", pitch))
        events.append((end_tick, "note_off", pitch))

    # Sort by time. If times are equal, put note_off before note_on to handle legato/overlaps cleanly
    # (though typically note_on priority over note_off is preferred if they are DIFFERENT notes, 
    # but for same note retriggering, off then on is vital. 
    # For different notes, order doesn't strictly matter for MIDI spec, but off-first is safer for monophonic synths).
    # Tuple comparison: (tick, type=="note_on", pitch). 
    # "note_off" == "note_on" is False (0), "note_on" == "note_on" is True (1).
    # So (tick, 0) comes before (tick, 1) -> note_off comes before note_on.
    events.sort(key=lambda e: (e[0], e[1] == "note_on"))

    current_tick = 0
    for tick, event_type, pitch in events:
        delta = max(0, tick - current_tick)
        vel = velocity if event_type == "note_on" else 0
        track.append(Message(event_type, note=int(pitch), velocity=vel, time=delta, channel=channel))
        current_tick = tick


def _tempo_messages(bpm: float) -> Tuple[MetaMessage, MetaMessage]:
    tempo = bpm2tempo(max(bpm, 1))
    return (
        MetaMessage("set_tempo", tempo=int(tempo), time=0),
        MetaMessage("time_signature", time=0, **TIME_SIGNATURE),
    )


def notes_to_midi_bytes(notes: Iterable[Note], *, bpm: float, program: int = 0, channel: int = 0, ticks_per_beat: int = DEFAULT_TICKS_PER_BEAT) -> bytes:
    mid = MidiFile(type=0, ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)

    for msg in _tempo_messages(bpm):
        track.append(msg)
    track.append(Message("program_change", program=program, channel=channel, time=0))

    _append_notes(track, notes, channel=channel, ticks_per_beat=ticks_per_beat)
    track.append(MetaMessage("end_of_track", time=0))

    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()


def write_multi_track(midis: Iterable[Iterable[Note]], *, bpm: float, path: str, program: int = 0, ticks_per_beat: int = DEFAULT_TICKS_PER_BEAT) -> str:
    mid = MidiFile(type=1, ticks_per_beat=ticks_per_beat)

    tempo_track = MidiTrack()
    mid.tracks.append(tempo_track)
    for msg in _tempo_messages(bpm):
        tempo_track.append(msg)
    tempo_track.append(MetaMessage("end_of_track", time=0))

    for idx, notes in enumerate(midis, start=1):
        channel = (idx - 1) % 16
        track = MidiTrack()
        track.append(MetaMessage("track_name", name=f"hook_{idx}", time=0))
        track.append(Message("program_change", program=program, channel=channel, time=0))
        _append_notes(track, notes, channel=channel, ticks_per_beat=ticks_per_beat)
        track.append(MetaMessage("end_of_track", time=0))
        mid.tracks.append(track)

    mid.save(path)
    return path


def _note_unit_seconds(bpm: float) -> float:
    beat_seconds = 60.0 / max(bpm, 1.0)
    return beat_seconds / 4.0  # 16th-note resolution


def _notes_to_audio_array(notes: Iterable[Note], *, bpm: float, sample_rate: int) -> np.ndarray:
    unit = _note_unit_seconds(bpm)
    tail_seconds = unit
    if not notes:
        total_samples = int(sample_rate * tail_seconds)
        return np.zeros(max(total_samples, sample_rate // 10), dtype=np.float32)

    notes = list(notes)
    end_16th = max(onset + duration for onset, duration, _ in notes)
    total_seconds = (end_16th * unit) + tail_seconds
    total_samples = max(int(np.ceil(total_seconds * sample_rate)), 1)
    audio = np.zeros(total_samples, dtype=np.float32)

    attack_samples = max(int(0.01 * sample_rate), 1)
    release_samples = max(int(0.02 * sample_rate), 1)

    for onset, duration, pitch in notes:
        start_idx = int(round(onset * unit * sample_rate))
        span = max(int(round(duration * unit * sample_rate)), 1)
        end_idx = min(start_idx + span, total_samples)
        if end_idx <= start_idx:
            continue

        segment_len = end_idx - start_idx
        t = np.arange(segment_len, dtype=np.float32) / sample_rate
        freq = 440.0 * (2.0 ** ((pitch - 69) / 12.0))
        envelope = np.ones(segment_len, dtype=np.float32)

        atk = min(attack_samples, segment_len)
        if atk > 0:
            envelope[:atk] *= np.linspace(0.0, 1.0, atk, endpoint=False, dtype=np.float32)

        rel = min(release_samples, segment_len)
        if rel > 0:
            envelope[-rel:] *= np.linspace(1.0, 0.0, rel, endpoint=False, dtype=np.float32)

        tone = 0.35 * np.sin(2.0 * np.pi * freq * t).astype(np.float32) * envelope
        audio[start_idx:end_idx] += tone

    return np.clip(audio, -1.0, 1.0)


def _float_audio_to_wav_bytes(audio: np.ndarray, *, sample_rate: int) -> bytes:
    if audio.size == 0:
        audio = np.zeros(sample_rate // 10, dtype=np.float32)
    pcm = np.clip(audio, -1.0, 1.0)
    frames = (pcm * 32767.0).astype(np.int16).tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return buf.getvalue()


def notes_to_wav_bytes(notes: Iterable[Note], *, bpm: float, sample_rate: int = 22050) -> bytes:
    audio = _notes_to_audio_array(notes, bpm=bpm, sample_rate=sample_rate)
    return _float_audio_to_wav_bytes(audio, sample_rate=sample_rate)


def hooks_to_wav_bytes(midis: Iterable[Iterable[Note]], *, bpm: float, sample_rate: int = 22050) -> bytes:
    tracks = [
        _notes_to_audio_array(notes, bpm=bpm, sample_rate=sample_rate)
        for notes in midis
    ]
    if not tracks:
        return notes_to_wav_bytes([], bpm=bpm, sample_rate=sample_rate)

    max_len = max(track.shape[0] for track in tracks)
    mix = np.zeros(max_len, dtype=np.float32)
    for track in tracks:
        mix[: track.shape[0]] += track

    if len(tracks) > 1:
        mix /= len(tracks)

    return _float_audio_to_wav_bytes(np.clip(mix, -1.0, 1.0), sample_rate=sample_rate)
