#!/usr/bin/env python3
"""
Batch evaluate genre classifier on all examples.

Tests genre classification across all audio files in the examples directory
and reports accuracy statistics.

Usage:
  python evaluate_genres.py
  python evaluate_genres.py /path/to/examples/
"""

import sys
from pathlib import Path

import librosa
from hookgen_core import (
    classify_genre,
    estimate_bpm_and_beats,
    groove_histogram,
    ticks_from_beats,
)

# Expected labels for golden files (add as you validate)
EXPECTED_LABELS: dict[str, str] = {
    # "fouronthefloor_124bpm.wav": "house_four_on_floor",
    # "reggaeton_96bpm.wav": "reggaeton_dembow",
    # "halftime_70bpm.wav": "trap_halftime",
    # "straight_120bpm.wav": "house_four_on_floor",
}


def main():
    # Get examples directory
    if len(sys.argv) > 1:
        examples_dir = Path(sys.argv[1])
    else:
        examples_dir = Path(__file__).parent.parent / "examples"

    if not examples_dir.exists():
        print(f"Examples directory not found: {examples_dir}")
        sys.exit(1)

    wav_files = sorted(examples_dir.glob("*.wav"))
    if not wav_files:
        print(f"No .wav files found in {examples_dir}")
        sys.exit(1)

    print(f"Evaluating {len(wav_files)} audio files...")
    print(f"{'='*90}")

    results = []

    for wav_file in wav_files:
        try:
            print(f"Processing {wav_file.name}...", end=" ", flush=True)

            # Load and analyze
            y, sr_raw = librosa.load(wav_file, sr=22050, mono=True, duration=8)
            sr = int(sr_raw)
            bpm, beat_times = estimate_bpm_and_beats(y, sr)
            ticks = ticks_from_beats(beat_times, subdiv=4)
            histogram = groove_histogram(y, sr, ticks)

            # Classify
            result = classify_genre(bpm, histogram)

            expected = EXPECTED_LABELS.get(wav_file.name)
            correct = (
                expected in result.tags if expected else None
            )

            results.append({
                "file": wav_file.name,
                "expected": expected,
                "predicted": result.tags[0],
                "confidence": result.confidence,
                "correct": correct,
            })

            if expected is None:
                status = "?"
                detail = "No expectation"
            elif correct:
                status = "✓"
                detail = "Correct"
            else:
                status = "✗"
                detail = f"Expected {expected}"

            print(
                f"{status} {result.tags[0]:25s} "
                f"Conf: {result.confidence:6.1%} | {detail}"
            )

        except Exception as e:
            print(f"✗ Error: {str(e)}")
            results.append({
                "file": wav_file.name,
                "expected": EXPECTED_LABELS.get(wav_file.name),
                "predicted": None,
                "confidence": 0.0,
                "correct": False,
                "error": str(e),
            })

    # Summary
    print(f"\n{'='*90}")
    print("SUMMARY")
    print(f"{'='*90}")

    labeled = [r for r in results if r["correct"] is not None]
    if labeled:
        correct_count = sum(1 for r in labeled if r["correct"])
        accuracy = correct_count / len(labeled)
        print(f"Labeled Files:    {len(labeled)}")
        print(f"Correct:          {correct_count} / {len(labeled)}")
        print(f"Accuracy:         {accuracy:.1%}")

    unlabeled = [r for r in results if r["correct"] is None]
    if unlabeled:
        print(f"\nUnlabeled Files:  {len(unlabeled)}")
        for r in unlabeled:
            if "error" not in r:
                print(f"  - {r['file']:40s} → {r['predicted']:25s} "
                      f"({r['confidence']:.1%})")

    errors = [r for r in results if "error" in r]
    if errors:
        print(f"\nErrors:           {len(errors)}")
        for r in errors:
            print(f"  - {r['file']:40s} → {r.get('error', 'Unknown')}")

    # Save detailed results to JSON
    import json
    results_file = examples_dir.parent / "genre_evaluation_results.json"
    with open(results_file, "w") as f:
        json.dump(
            [
                {k: v for k, v in r.items() if k != "error"}
                for r in results
            ],
            f,
            indent=2,
        )
    print(f"\nDetailed results saved to: {results_file}")


if __name__ == "__main__":
    main()
