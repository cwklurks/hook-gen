#!/usr/bin/env python3
"""
Genre classifier tuning script.

Analyzes a single audio file and shows detailed genre classification results,
useful for debugging and tuning the classifier.

Usage:
  python tune_genre.py /path/to/audio.wav --expected house_four_on_floor
  python tune_genre.py /path/to/audio.wav --output-template
"""

import argparse
import sys

import librosa
import numpy as np
from hookgen_core import (
    GENRE_TEMPLATES,
    classify_genre,
    estimate_bpm_and_beats,
    groove_histogram,
    ticks_from_beats,
)


def format_histogram(h: np.ndarray) -> str:
    """Format histogram for display."""
    return "[" + ", ".join(f"{v:.2f}" for v in h) + "]"


def main():
    parser = argparse.ArgumentParser(description="Debug and tune genre classification")
    parser.add_argument("audio_file", help="Path to audio file")
    parser.add_argument(
        "--expected",
        help="Expected genre tag (for validation)",
        default=None,
    )
    parser.add_argument(
        "--output-template",
        help="Output extracted histogram as a template",
        action="store_true",
    )
    args = parser.parse_args()

    # Load and analyze
    print(f"Loading {args.audio_file}...")
    try:
        y, sr_raw = librosa.load(args.audio_file, sr=22050, mono=True, duration=8)
        sr = int(sr_raw)
    except Exception as e:
        print(f"Error loading file: {e}")
        sys.exit(1)

    print("Detecting BPM...")
    bpm, beat_times = estimate_bpm_and_beats(y, sr)

    print("Extracting groove...")
    ticks = ticks_from_beats(beat_times, subdiv=4)
    histogram = groove_histogram(y, sr, ticks)

    print(f"\nBPM: {bpm:.1f}")
    print(f"Beat count: {len(beat_times)}")
    print(f"Histogram: {format_histogram(histogram)}")

    # Classify
    print("\nClassifying genre...")
    result = classify_genre(bpm, histogram)

    print(f"\n{'=' * 70}")
    print("GENRE CLASSIFICATION RESULT")
    print(f"{'=' * 70}")
    print(f"Tags: {', '.join(result.tags)}")
    print(f"Confidence: {result.confidence:.2%}")

    print("\nExplanation:")
    for i, bullet in enumerate(result.explanation, 1):
        print(f"  {i}. {bullet}")

    print("\nPreset Parameters (normalized 0-1):")
    for key, val in result.preset.items():
        print(f"  {key:15s}: {val:.2f}")

    # Debug info
    print(f"\n{'=' * 70}")
    print("DEBUG INFORMATION")
    print(f"{'=' * 70}")

    print("\nExtracted Features:")
    for key, val in sorted(result.debug["features"].items()):
        print(f"  {key:20s}: {val:8.4f}")

    print("\nGenre Scores:")
    for tag in sorted(result.debug["genre_breakdowns"].keys()):
        breakdown = result.debug["genre_breakdowns"][tag]
        print(f"\n  {tag}:")
        print(f"    Combined Score: {breakdown['combined_score']:8.4f}")
        print(
            f"    Template Sim:   {breakdown['template_similarity']:8.4f} "
            f"(shift={breakdown['best_shift']:+2d})"
        )
        print(
            f"    BPM Score:      {breakdown['bpm_score']:8.4f} ({breakdown['bpm_interpretation']})"
        )
        print(f"    Feature Match:  {breakdown['feature_match']:8.4f}")

    print("\nGenre Probabilities:")
    for tag, prob in sorted(result.debug["probabilities"].items(), key=lambda x: -x[1])[:5]:
        bar_width = int(prob * 40)
        bar = "█" * bar_width + "░" * (40 - bar_width)
        print(f"  {tag:25s} {bar} {prob:.2%}")

    print("\nConfidence Analysis:")
    print(f"  Top probability:     {result.debug['top_prob']:.2%}")
    print(f"  Second probability:  {result.debug['second_prob']:.2%}")
    print(f"  Probability gap:     {result.debug['prob_gap']:.2%}")

    # Check against expected
    if args.expected:
        print(f"\n{'=' * 70}")
        print("VALIDATION")
        print(f"{'=' * 70}")
        if args.expected in result.tags:
            print(f"✓ CORRECT: Expected {args.expected}, got {result.tags}")
        else:
            print(f"✗ INCORRECT: Expected {args.expected}, got {result.tags}")
            print("\nExpected tag breakdown:")
            if args.expected in result.debug["genre_breakdowns"]:
                breakdown = result.debug["genre_breakdowns"][args.expected]
                print(f"  Combined Score:  {breakdown['combined_score']:8.4f}")
                print(f"  Template Sim:    {breakdown['template_similarity']:8.4f}")
                print(f"  BPM Score:       {breakdown['bpm_score']:8.4f}")
                print(f"  Feature Match:   {breakdown['feature_match']:8.4f}")

                print(f"\nFeature Expectations for {args.expected}:")
                config = GENRE_TEMPLATES[args.expected]
                features = result.debug["features"]
                for (
                    feature_name,
                    (target, tol, _weight),
                ) in config["features"].items():  # type: ignore[attr-defined]
                    if feature_name in features:
                        actual = features[feature_name]
                        score = np.exp(-(((actual - target) / tol) ** 2))
                        diff = actual - target
                        status = "✓" if score > 0.7 else "✗"
                        print(
                            f"  {status} {feature_name:20s}: "
                            f"expected {target:.2f}, got {actual:.2f} "
                            f"(diff={diff:+.2f}, score={score:.2f})"
                        )
            else:
                print(f"  {args.expected} not in genre_breakdowns")

    # Output template
    if args.output_template:
        print(f"\n{'=' * 70}")
        print("EXTRACTED TEMPLATE")
        print(f"{'=' * 70}")
        print("Copy this into GENRE_TEMPLATES in genre.py:")
        print(f'"template": {list(histogram)},')

    print()


if __name__ == "__main__":
    main()
