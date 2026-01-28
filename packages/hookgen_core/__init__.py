"""HookGen Core - Shared music analysis and generation library."""

__version__ = "1.0.0"

# Export public API
from .export import (
    DEFAULT_TICKS_PER_BEAT,
    TIME_SIGNATURE,
    Note,
    hooks_to_wav_bytes,
    notes_to_midi_bytes,
    notes_to_wav_bytes,
    write_multi_track,
)
from .genre import (
    GENRE_TEMPLATES,
    GenreResult,
    classify_genre,
)
from .motif import (
    DEFAULT_SCALE,
    NOTE_TO_SEMITONE,
    SCALE_PATTERNS,
    SCALE_ROOTS,
    SCALE_TEMPLATES,
    assign_pitches,
    detect_scale_from_audio,
    generate_motif,
    generate_structured_hook,
    list_available_scales,
    midi_mapper,
    sample_rhythm,
    vary_motif,
)
from .rhythm import (
    estimate_bpm_and_beats,
    groove_histogram,
    load_mono,
    ticks_from_beats,
)
from .ui_helpers import (
    build_zip_name,
)

__all__ = [
    # rhythm
    "load_mono",
    "estimate_bpm_and_beats",
    "ticks_from_beats",
    "groove_histogram",
    # motif
    "SCALE_PATTERNS",
    "SCALE_ROOTS",
    "NOTE_TO_SEMITONE",
    "DEFAULT_SCALE",
    "SCALE_TEMPLATES",
    "list_available_scales",
    "sample_rhythm",
    "midi_mapper",
    "assign_pitches",
    "generate_motif",
    "vary_motif",
    "generate_structured_hook",
    "detect_scale_from_audio",
    # export
    "DEFAULT_TICKS_PER_BEAT",
    "TIME_SIGNATURE",
    "Note",
    "notes_to_midi_bytes",
    "write_multi_track",
    "notes_to_wav_bytes",
    "hooks_to_wav_bytes",
    # ui_helpers
    "build_zip_name",
    # genre
    "classify_genre",
    "GenreResult",
    "GENRE_TEMPLATES",
]




