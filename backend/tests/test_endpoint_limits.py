"""Request-boundary tests for public API models."""

import pytest
from api.endpoints import MidiRequest
from pydantic import ValidationError


def note(*, start: float = 0, duration: float = 1) -> dict[str, float | int]:
    return {
        "pitch": 60,
        "start": start,
        "duration": duration,
        "velocity": 100,
    }


def test_midi_export_accepts_generated_hook_bounds():
    request = MidiRequest(notes=[note(start=15.75, duration=0.25)], bpm=120)

    assert len(request.notes) == 1


@pytest.mark.parametrize(
    "notes",
    [
        [],
        [note()] * 257,
        [note(start=16.01)],
        [note(duration=16.01)],
    ],
)
def test_midi_export_rejects_unbounded_payloads(notes):
    with pytest.raises(ValidationError):
        MidiRequest(notes=notes, bpm=120)
