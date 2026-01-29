"""
Rhythm-based genre/style classification for Hook-Gen.

Classifies input grooves into style tags (house, reggaeton, trap, dnb, techno)
using template matching, BPM priors, and feature analysis. Returns confidence,
explanations, and preset parameters for the generator.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class GenreResult:
    """Result of genre classification."""

    tags: List[str]  # Top 1-3 genre tags
    confidence: float  # Overall confidence (0-1)
    explanation: List[str]  # 3-5 human-readable explanation bullets
    preset: Dict[str, float]  # Normalized preset values {density, syncopation, register}
    debug: Dict[str, Any] = field(default_factory=dict)  # Debug info for tuning

    def to_dict(self) -> dict:
        """Convert to API-friendly dict."""
        return {
            "tags": self.tags,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "preset": self.preset,
            "debug": self.debug,
        }


# Genre templates with rhythm patterns, BPM priors, feature expectations, and presets
GENRE_TEMPLATES = {
    "house_four_on_floor": {
        "template": [
            0.22,
            0.02,
            0.03,
            0.02,
            0.21,
            0.02,
            0.03,
            0.02,
            0.21,
            0.02,
            0.03,
            0.02,
            0.21,
            0.02,
            0.03,
            0.02,
        ],
        "bpm_prior": (124.0, 8.0),
        "features": {
            "onbeat_energy": (0.60, 0.15, 1.0),
            "backbeat_energy": (0.25, 0.10, 0.8),
            "sync_ratio": (0.25, 0.15, 0.6),
            "density": (0.45, 0.20, 0.5),
        },
        "preset": {
            "density": 0.55,
            "syncopation": 0.20,
            "register": 0.50,
        },
        "description": "four-on-the-floor kick pattern typical of house music",
    },
    "reggaeton_dembow": {
        "template": [
            0.15,
            0.03,
            0.05,
            0.12,
            0.10,
            0.03,
            0.15,
            0.02,
            0.15,
            0.03,
            0.05,
            0.12,
            0.10,
            0.03,
            0.02,
            0.02,
        ],
        "bpm_prior": (96.0, 6.0),
        "features": {
            "onbeat_energy": (0.40, 0.15, 0.9),
            "backbeat_energy": (0.20, 0.10, 0.7),
            "sync_ratio": (0.50, 0.20, 1.0),
            "density": (0.55, 0.20, 0.6),
        },
        "preset": {
            "density": 0.65,
            "syncopation": 0.45,
            "register": 0.50,
        },
        "description": "dembow rhythm pattern characteristic of reggaeton",
    },
    "trap_halftime": {
        "template": [
            0.18,
            0.03,
            0.08,
            0.03,
            0.15,
            0.03,
            0.10,
            0.03,
            0.18,
            0.03,
            0.08,
            0.03,
            0.05,
            0.03,
            0.02,
            0.02,
        ],
        "bpm_prior": (140.0, 12.0),
        "features": {
            "onbeat_energy": (0.35, 0.15, 0.8),
            "backbeat_energy": (0.15, 0.10, 0.9),
            "sync_ratio": (0.60, 0.20, 1.0),
            "density": (0.40, 0.20, 0.7),
        },
        "preset": {
            "density": 0.40,
            "syncopation": 0.55,
            "register": 0.65,
        },
        "description": "half-time feel with sparse, syncopated hi-hats typical of trap",
    },
    "dnb_breakbeat": {
        "template": [
            0.12,
            0.06,
            0.09,
            0.06,
            0.11,
            0.06,
            0.08,
            0.06,
            0.10,
            0.06,
            0.08,
            0.06,
            0.07,
            0.05,
            0.03,
            0.02,
        ],
        "bpm_prior": (174.0, 8.0),
        "features": {
            "onbeat_energy": (0.35, 0.15, 0.7),
            "backbeat_energy": (0.20, 0.10, 0.7),
            "sync_ratio": (0.70, 0.20, 1.0),
            "density": (0.70, 0.20, 0.9),
            "entropy": (2.4, 0.3, 0.8),
        },
        "preset": {
            "density": 0.75,
            "syncopation": 0.60,
            "register": 0.55,
        },
        "description": "complex breakbeat pattern with fast BPM typical of drum & bass",
    },
    "techno_driving": {
        "template": [
            0.21,
            0.03,
            0.04,
            0.03,
            0.20,
            0.03,
            0.04,
            0.03,
            0.20,
            0.03,
            0.04,
            0.03,
            0.20,
            0.03,
            0.04,
            0.03,
        ],
        "bpm_prior": (130.0, 10.0),
        "features": {
            "onbeat_energy": (0.62, 0.15, 1.0),
            "backbeat_energy": (0.22, 0.10, 0.6),
            "sync_ratio": (0.28, 0.15, 0.5),
            "density": (0.48, 0.20, 0.5),
        },
        "preset": {
            "density": 0.58,
            "syncopation": 0.25,
            "register": 0.50,
        },
        "description": "relentless four-on-the-floor with industrial drive",
    },
}

# Confidence thresholds
CONFIDENCE_THRESHOLD = 0.45
AMBIGUITY_THRESHOLD = 0.12


# ============================================================================
# FEATURE EXTRACTION
# ============================================================================


def extract_rhythm_features(histogram: np.ndarray, bpm: float) -> Dict[str, float]:
    """
    Extract interpretable rhythm features from histogram and BPM.

    Args:
        histogram: 16-element groove histogram (normalized to sum=1.0)
        bpm: Detected tempo in BPM

    Returns:
        Dictionary of feature values
    """
    h = np.asarray(histogram, dtype=float).copy()

    # Ensure normalized
    if h.sum() > 0:
        h = h / h.sum()
    else:
        h = np.ones(16) / 16.0

    features = {}

    # 1. Density: fraction of bins above threshold
    threshold = 0.01
    features["density"] = float(np.sum(h > threshold) / 16.0)

    # 2. Onbeat energy: sum of quarter note positions (0,4,8,12)
    features["onbeat_energy"] = float(h[0] + h[4] + h[8] + h[12])

    # 3. Backbeat energy: snare positions (4, 12 in 16th grid)
    features["backbeat_energy"] = float(h[4] + h[12])

    # 4. Syncopation ratio: weak beats / strong beats
    strong_indices = [0, 4, 8, 12]
    weak_indices = [i for i in range(16) if i not in strong_indices]

    strong_sum = h[strong_indices].sum()
    weak_sum = h[weak_indices].sum()

    if strong_sum > 1e-10:
        features["sync_ratio"] = float(weak_sum / strong_sum)
    else:
        features["sync_ratio"] = 1.0

    # 5. Entropy: measure of rhythm spread
    h_safe = h + 1e-10
    features["entropy"] = float(-np.sum(h_safe * np.log(h_safe)))

    # 6. BPM value
    features["bpm"] = float(bpm)

    return features


# ============================================================================
# TEMPLATE MATCHING
# ============================================================================


def compute_template_similarity(
    histogram: np.ndarray,
    template: np.ndarray,
    search_shifts: Optional[List[int]] = None,
) -> Tuple[float, int]:
    """
    Compute best cosine similarity with circular shift search.

    Args:
        histogram: Input 16-element groove histogram
        template: Template 16-element histogram
        search_shifts: Shift amounts to test (in 16th notes)

    Returns:
        (best_similarity, best_shift)
    """
    if search_shifts is None:
        search_shifts = [-1, 0, 1]

    h = np.asarray(histogram, dtype=float).copy()
    t = np.asarray(template, dtype=float).copy()

    # Normalize both to unit vectors
    h_norm = h / (np.linalg.norm(h) + 1e-9)
    t_norm = t / (np.linalg.norm(t) + 1e-9)

    best_sim = -1.0
    best_shift = 0

    for shift in search_shifts:
        h_shifted = np.roll(h_norm, shift)
        sim = float(np.dot(h_shifted, t_norm))

        if sim > best_sim:
            best_sim = sim
            best_shift = shift

    return best_sim, best_shift


# ============================================================================
# BPM SCORING
# ============================================================================


def compute_bpm_score(bpm: float, center: float, sigma: float) -> Tuple[float, float, str]:
    """
    Compute BPM match score with half/double time detection.

    Args:
        bpm: Detected BPM
        center: Expected BPM center
        sigma: BPM tolerance (std dev)

    Returns:
        (best_score, adjusted_bpm, interpretation)
    """
    candidates = [
        (bpm, "straight"),
        (bpm * 2.0, "double-time"),
        (bpm * 0.5, "half-time"),
    ]

    best_score = 0.0
    best_bpm = bpm
    best_interp = "straight"

    for test_bpm, interp in candidates:
        # Gaussian score
        score = np.exp(-(((test_bpm - center) / sigma) ** 2))

        if score > best_score:
            best_score = score
            best_bpm = test_bpm
            best_interp = interp

    return float(best_score), float(best_bpm), best_interp


# ============================================================================
# FEATURE MATCHING
# ============================================================================


def compute_feature_match_score(
    features: Dict[str, float], expectations: Dict[str, Tuple[float, float, float]]
) -> Dict[str, float]:
    """
    Compute weighted feature match scores.

    Args:
        features: Extracted feature values
        expectations: {feature_name: (target, tolerance, weight)}

    Returns:
        Dictionary with individual match scores and aggregated score
    """
    scores = {}
    weighted_sum = 0.0
    total_weight = 0.0

    for feature_name, (target, tolerance, weight) in expectations.items():
        if feature_name not in features:
            continue

        value = features[feature_name]

        # Gaussian match: exp(-((value - target) / tolerance)^2)
        diff = abs(value - target)
        match = np.exp(-((diff / tolerance) ** 2))

        scores[feature_name] = float(match)
        weighted_sum += match * weight
        total_weight += weight

    # Aggregate score
    if total_weight > 0:
        scores["aggregate"] = float(weighted_sum / total_weight)
    else:
        scores["aggregate"] = 0.0

    return scores


# ============================================================================
# MAIN CLASSIFICATION
# ============================================================================


def classify_genre(
    bpm: float,
    histogram: np.ndarray,
    top_k: int = 3,
    temperature: float = 2.0,
) -> GenreResult:
    """
    Classify genre from BPM and groove histogram.

    Args:
        bpm: Detected tempo in BPM
        histogram: 16-element groove histogram (normalized to sum=1.0)
        top_k: Number of top tags to return (default 3)
        temperature: Softmax temperature for probability sharpening

    Returns:
        GenreResult with tags, confidence, explanation, preset, and debug info
    """
    # Validate and normalize histogram
    h = np.asarray(histogram, dtype=float).copy()
    if not np.isfinite(h).all() or h.sum() <= 0:
        h = np.ones(16) / 16.0
    else:
        h = h / h.sum()

    # Extract features
    features = extract_rhythm_features(h, bpm)

    # Score each genre
    genre_scores = {}
    debug_info = {
        "features": features,
        "genre_breakdowns": {},
    }

    for tag, config in GENRE_TEMPLATES.items():  # type: ignore[attr-defined]
        # 1. Template matching (55% weight)
        template = np.array(config["template"])  # type: ignore[index]
        template_sim, best_shift = compute_template_similarity(h, template)

        # 2. BPM prior (25% weight)
        bpm_prior = config["bpm_prior"]  # type: ignore[index]
        bpm_center = float(bpm_prior[0])  # type: ignore[index]
        bpm_sigma = float(bpm_prior[1])  # type: ignore[index]
        bpm_score, adjusted_bpm, bpm_interp = compute_bpm_score(bpm, bpm_center, bpm_sigma)

        # 3. Feature matching (20% weight)
        feature_expectations: Dict[str, Tuple[float, float, float]] = {
            k: (float(v[0]), float(v[1]), float(v[2]))
            for k, v in config["features"].items()  # type: ignore[attr-defined]
        }
        feature_scores = compute_feature_match_score(features, feature_expectations)
        feature_match = feature_scores["aggregate"]

        # Combined score
        combined = 0.55 * template_sim + 0.25 * bpm_score + 0.20 * feature_match

        genre_scores[tag] = combined

        # Store debug info
        debug_info["genre_breakdowns"][tag] = {  # type: ignore[index, assignment]
            "template_similarity": float(template_sim),
            "best_shift": int(best_shift),
            "bpm_score": float(bpm_score),
            "adjusted_bpm": float(adjusted_bpm),
            "bpm_interpretation": bpm_interp,
            "feature_match": float(feature_match),
            "feature_scores": feature_scores,
            "combined_score": float(combined),
        }

    # Convert to probabilities with softmax
    scores_array = np.array(list(genre_scores.values()))
    tags_array = np.array(list(genre_scores.keys()))

    # Apply temperature-scaled softmax
    exp_scores = np.exp(scores_array / temperature)
    probabilities = exp_scores / exp_scores.sum()

    # Sort by probability
    sorted_indices = np.argsort(probabilities)[::-1]
    sorted_tags = tags_array[sorted_indices]
    sorted_probs = probabilities[sorted_indices]

    # Check confidence thresholds
    top_prob = sorted_probs[0]
    second_prob = sorted_probs[1] if len(sorted_probs) > 1 else 0.0
    prob_gap = top_prob - second_prob

    debug_info["probabilities"] = dict(  # type: ignore[assignment]
        {tag: float(prob) for tag, prob in zip(sorted_tags, sorted_probs, strict=False)}
    )
    debug_info["top_prob"] = top_prob  # type: ignore[assignment]
    debug_info["second_prob"] = second_prob  # type: ignore[assignment]
    debug_info["prob_gap"] = prob_gap  # type: ignore[assignment]

    # Determine tags and explanations
    if top_prob < CONFIDENCE_THRESHOLD or prob_gap < AMBIGUITY_THRESHOLD:
        # Low confidence or ambiguous → return "unknown"
        result_tags = ["unknown"]
        confidence = float(top_prob)
        explanation = _generate_unknown_explanation(features, top_prob, prob_gap, sorted_tags[0])
        preset = _get_default_preset()
    else:
        # Return top K tags above threshold
        threshold = 0.15
        result_tags = [
            tag for tag, prob in zip(sorted_tags, sorted_probs, strict=False) if prob > threshold
        ][:top_k]
        confidence = float(top_prob)

        # Generate explanation for top tag
        top_tag = result_tags[0]
        genre_breakdown: Dict[str, Any] = debug_info["genre_breakdowns"][top_tag]  # type: ignore[index, assignment]
        genre_config: Dict[str, Any] = dict(GENRE_TEMPLATES[top_tag])  # type: ignore[arg-type]
        explanation = _generate_explanation(
            top_tag,
            features,
            genre_breakdown,
            genre_config,
        )

        # Get preset from top tag
        preset_data = GENRE_TEMPLATES[top_tag]["preset"]  # type: ignore[index]
        preset = dict(preset_data)  # type: ignore[arg-type]

    return GenreResult(
        tags=result_tags,
        confidence=confidence,
        explanation=explanation,
        preset=preset,
        debug=debug_info,
    )


# ============================================================================
# EXPLANATION GENERATION
# ============================================================================


def _generate_explanation(
    tag: str,
    features: Dict[str, float],
    breakdown: Dict[str, Any],
    config: Dict[str, Any],
) -> List[str]:
    """Generate human-readable explanation bullets."""
    explanation = []

    # 1. Genre description
    explanation.append(f"Detected {config['description']}")

    # 2. BPM interpretation
    bpm_val = features["bpm"]
    bpm_interp = breakdown["bpm_interpretation"]
    adjusted = breakdown["adjusted_bpm"]

    if bpm_interp == "straight":
        explanation.append(
            f"Tempo {bpm_val:.0f} BPM matches "
            f"{tag.replace('_', ' ')} prior "
            f"({config['bpm_prior'][0]:.0f} BPM)"
        )
    elif bpm_interp == "half-time":
        explanation.append(
            f"Tempo {bpm_val:.0f} BPM suggests half-time feel (effective {adjusted:.0f} BPM)"
        )
    elif bpm_interp == "double-time":
        explanation.append(
            f"Tempo {bpm_val:.0f} BPM suggests double-time feel (effective {adjusted:.0f} BPM)"
        )

    # 3. Rhythm characteristics
    onbeat = features["onbeat_energy"]
    sync_ratio = features["sync_ratio"]

    if onbeat > 0.55:
        explanation.append(f"Strong quarter-note pulse (onbeat energy {onbeat:.2f})")
    elif onbeat < 0.35:
        explanation.append(f"Sparse onbeat hits (onbeat energy {onbeat:.2f})")

    if sync_ratio > 0.55:
        explanation.append(f"High syncopation (sync ratio {sync_ratio:.2f})")
    elif sync_ratio < 0.35:
        explanation.append("Low syncopation, groove locks to strong beats")

    # 4. Template match quality
    template_sim = breakdown["template_similarity"]
    explanation.append(f"Rhythm pattern similarity: {template_sim:.1%}")

    return explanation[:5]  # Max 5 bullets


def _generate_unknown_explanation(
    features: Dict[str, float], top_prob: float, prob_gap: float, closest_tag: str
) -> List[str]:
    """Generate explanation for unknown classification."""
    explanation = []

    if top_prob < CONFIDENCE_THRESHOLD:
        explanation.append(f"Confidence too low ({top_prob:.1%} < {CONFIDENCE_THRESHOLD:.1%})")

    if prob_gap < AMBIGUITY_THRESHOLD:
        explanation.append(f"Ambiguous rhythm (top genres too close: gap={prob_gap:.1%})")

    explanation.append(f"Closest match: {closest_tag.replace('_', ' ')} ({top_prob:.1%})")

    # Add basic rhythm characteristics
    bpm = features["bpm"]
    density = features["density"]
    sync_ratio = features["sync_ratio"]

    explanation.append(
        f"Tempo: {bpm:.0f} BPM, Density: {density:.1%}, Syncopation: {sync_ratio:.2f}"
    )

    return explanation


def _get_default_preset() -> Dict[str, float]:
    """Return default preset for unknown genres."""
    return {
        "density": 0.50,
        "syncopation": 0.40,
        "register": 0.50,
    }
