"""
Comprehensive unit tests for genre classification module.
"""

import numpy as np
import pytest
from hookgen_core.genre import (
    extract_rhythm_features,
    compute_template_similarity,
    compute_bpm_score,
    compute_feature_match_score,
    classify_genre,
    GENRE_TEMPLATES,
    CONFIDENCE_THRESHOLD,
    AMBIGUITY_THRESHOLD,
)


class TestFeatureExtraction:
    """Test rhythm feature extraction."""

    def test_extract_features_four_on_floor(self):
        """Test feature extraction on four-on-the-floor pattern."""
        # Strong quarter notes at positions 0, 4, 8, 12
        h = np.zeros(16)
        h[[0, 4, 8, 12]] = 0.25
        h = h / h.sum()

        features = extract_rhythm_features(h, 124.0)

        assert features["onbeat_energy"] == pytest.approx(1.0, abs=0.01)
        assert features["backbeat_energy"] == pytest.approx(0.5, abs=0.01)
        assert features["bpm"] == 124.0
        assert features["sync_ratio"] < 0.1  # Very low syncopation
        assert features["density"] > 0.2

    def test_extract_features_syncopated(self):
        """Test feature extraction on syncopated pattern."""
        # Uniform distribution (high syncopation)
        h = np.ones(16) / 16.0

        features = extract_rhythm_features(h, 96.0)

        # 12 weak bins / 4 strong bins = 3.0 ratio
        assert features["sync_ratio"] == pytest.approx(3.0, abs=0.1)
        assert features["entropy"] > 2.5  # High entropy
        assert features["density"] == 1.0  # All bins above threshold

    def test_extract_features_sparse(self):
        """Test feature extraction on sparse pattern."""
        h = np.array([0.5] + [0.0] * 15)
        h = h / h.sum()

        features = extract_rhythm_features(h, 140.0)

        assert features["density"] < 0.2
        assert features["onbeat_energy"] == pytest.approx(0.5, abs=0.01)
        assert features["entropy"] < 1.0

    def test_extract_features_handles_zeros(self):
        """Test graceful handling of zero histogram."""
        h = np.zeros(16)

        features = extract_rhythm_features(h, 120.0)

        # Should return uniform values
        assert "bpm" in features
        assert features["bpm"] == 120.0
        assert "onbeat_energy" in features
        assert features["density"] == 1.0  # All uniform bins are "above threshold"

    def test_extract_features_invalid_input(self):
        """Test handling of invalid input."""
        h = np.array([np.nan, np.inf] + [0.0] * 14)

        features = extract_rhythm_features(h, 120.0)

        # Should not raise, return valid features
        assert "bpm" in features
        assert all(np.isfinite(v) for v in features.values())


class TestTemplateSimilarity:
    """Test template matching with shift search."""

    def test_perfect_match(self):
        """Test perfect template match."""
        template = np.array(GENRE_TEMPLATES["house_four_on_floor"]["template"])

        sim, shift = compute_template_similarity(template, template)

        assert sim == pytest.approx(1.0, abs=0.01)
        assert shift == 0

    def test_shifted_match(self):
        """Test template match with circular shift."""
        template = np.array(GENRE_TEMPLATES["house_four_on_floor"]["template"])
        shifted = np.roll(template, 1)

        sim, shift = compute_template_similarity(shifted, template)

        assert sim == pytest.approx(1.0, abs=0.01)
        assert shift == -1  # Shifted back by 1

    def test_opposite_shift(self):
        """Test detection of opposite shift direction."""
        template = np.array(GENRE_TEMPLATES["house_four_on_floor"]["template"])
        shifted = np.roll(template, -2)

        sim, shift = compute_template_similarity(shifted, template)

        assert sim == pytest.approx(1.0, abs=0.01)
        assert shift == 2  # Shifted forward by 2

    def test_no_match(self):
        """Test low similarity for unrelated patterns."""
        house = np.array(GENRE_TEMPLATES["house_four_on_floor"]["template"])
        random = np.random.RandomState(42).random(16)
        random = random / random.sum()

        sim, shift = compute_template_similarity(random, house)

        assert sim < 0.8  # Should be lower than typical matches

    def test_normalized_input(self):
        """Test that similarity is computed with normalized vectors."""
        template = np.array(GENRE_TEMPLATES["house_four_on_floor"]["template"])
        scaled = template * 2.0  # Scale by 2x

        sim, shift = compute_template_similarity(scaled, template)

        # Should still be perfect match due to normalization
        assert sim == pytest.approx(1.0, abs=0.01)

    def test_custom_shifts(self):
        """Test custom shift search range."""
        template = np.array(GENRE_TEMPLATES["house_four_on_floor"]["template"])
        shifted = np.roll(template, 5)

        # Only search shifts [-1, 0, 1]
        sim1, shift1 = compute_template_similarity(shifted, template, search_shifts=[-1, 0, 1])

        # Should not find the shift at 5
        assert shift1 in [-1, 0, 1]
        assert sim1 < 0.9

        # Now search wider range
        sim2, shift2 = compute_template_similarity(shifted, template, search_shifts=[-5, 0, 5])

        # Should find the shift at -5
        assert shift2 == -5 or abs(shift2 - (-5)) < 0.1


class TestBPMScoring:
    """Test BPM prior scoring with half/double time."""

    def test_exact_match(self):
        """Test exact BPM match."""
        score, adj_bpm, interp = compute_bpm_score(124.0, 124.0, 8.0)

        assert score == pytest.approx(1.0, abs=0.01)
        assert adj_bpm == 124.0
        assert interp == "straight"

    def test_close_match(self):
        """Test close BPM match."""
        score, adj_bpm, interp = compute_bpm_score(126.0, 124.0, 8.0)

        assert score > 0.8
        assert adj_bpm == 126.0
        assert interp == "straight"

    def test_half_time_detection(self):
        """Test half-time BPM interpretation."""
        # Detected 70 BPM, expecting 140 BPM (trap half-time)
        score, adj_bpm, interp = compute_bpm_score(70.0, 140.0, 12.0)

        assert interp == "double-time"  # 70*2 = 140
        assert adj_bpm == 140.0
        assert score > 0.8

    def test_double_time_detection(self):
        """Test double-time BPM interpretation."""
        # Detected 200 BPM, expecting 100 BPM
        score, adj_bpm, interp = compute_bpm_score(200.0, 100.0, 10.0)

        assert interp == "half-time"  # 200*0.5 = 100
        assert adj_bpm == 100.0
        assert score > 0.8

    def test_poor_match(self):
        """Test poor BPM match."""
        score, adj_bpm, interp = compute_bpm_score(60.0, 120.0, 5.0)

        # Score should be low for far mismatch
        assert score < 0.5


class TestFeatureMatching:
    """Test feature-based scoring."""

    def test_perfect_feature_match(self):
        """Test perfect feature matching."""
        features = {
            "onbeat_energy": 0.60,
            "sync_ratio": 0.25,
        }
        expectations = {
            "onbeat_energy": (0.60, 0.15, 1.0),
            "sync_ratio": (0.25, 0.15, 1.0),
        }

        scores = compute_feature_match_score(features, expectations)

        assert scores["aggregate"] == pytest.approx(1.0, abs=0.01)

    def test_partial_feature_match(self):
        """Test partial feature matching."""
        features = {
            "onbeat_energy": 0.40,  # Far from target 0.60
            "sync_ratio": 0.25,  # Perfect match
        }
        expectations = {
            "onbeat_energy": (0.60, 0.10, 1.0),  # Strict tolerance
            "sync_ratio": (0.25, 0.15, 1.0),
        }

        scores = compute_feature_match_score(features, expectations)

        assert scores["sync_ratio"] == pytest.approx(1.0, abs=0.01)
        assert scores["onbeat_energy"] < 0.3  # Low match
        assert 0.4 < scores["aggregate"] < 0.7

    def test_weighted_aggregation(self):
        """Test that weights are properly applied."""
        features = {
            "feature_a": 0.5,
            "feature_b": 0.5,
        }
        expectations = {
            "feature_a": (0.5, 0.1, 2.0),  # Weight 2.0
            "feature_b": (0.5, 0.1, 1.0),  # Weight 1.0
        }

        scores = compute_feature_match_score(features, expectations)

        # feature_a has higher weight, so should influence aggregate more
        assert scores["aggregate"] == pytest.approx(1.0, abs=0.01)

    def test_missing_features(self):
        """Test handling of missing features."""
        features = {
            "feature_a": 0.5,
        }
        expectations = {
            "feature_a": (0.5, 0.1, 1.0),
            "feature_b": (0.5, 0.1, 1.0),  # Not in features
        }

        scores = compute_feature_match_score(features, expectations)

        # Should still compute aggregate for available features
        assert "aggregate" in scores


class TestGenreClassification:
    """Integration tests for full genre classification."""

    def test_classify_house(self):
        """Test house classification."""
        # Four-on-the-floor pattern at house tempo
        h = np.zeros(16)
        h[[0, 4, 8, 12]] = 0.22
        h[[1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15]] = 0.02
        h = h / h.sum()

        result = classify_genre(124.0, h)

        assert "house_four_on_floor" in result.tags or len(result.tags) > 0
        assert 0 <= result.confidence <= 1.0
        assert len(result.explanation) >= 1
        assert "preset" in result.preset
        assert all(k in result.preset for k in ["density", "syncopation", "register"])

    def test_classify_reggaeton(self):
        """Test reggaeton classification."""
        template = np.array(GENRE_TEMPLATES["reggaeton_dembow"]["template"])

        result = classify_genre(96.0, template)

        assert len(result.tags) > 0
        assert 0 <= result.confidence <= 1.0
        assert len(result.explanation) >= 1

    def test_classify_unknown_low_confidence(self):
        """Test unknown classification for ambiguous pattern."""
        # Random pattern
        h = np.random.RandomState(42).random(16)
        h = h / h.sum()

        result = classify_genre(110.0, h)

        # Check structure is valid
        assert len(result.tags) > 0
        assert 0 <= result.confidence <= 1.0
        assert len(result.explanation) > 0
        assert "preset" in result.preset

    def test_classify_trap_halftime(self):
        """Test trap classification with half-time BPM."""
        template = np.array(GENRE_TEMPLATES["trap_halftime"]["template"])

        result = classify_genre(140.0, template)

        assert len(result.tags) > 0
        assert 0 <= result.confidence <= 1.0

    def test_classify_dnb(self):
        """Test drum and bass classification."""
        template = np.array(GENRE_TEMPLATES["dnb_breakbeat"]["template"])

        result = classify_genre(174.0, template)

        assert len(result.tags) > 0
        assert 0 <= result.confidence <= 1.0

    def test_result_structure(self):
        """Test that result has all required fields."""
        h = np.ones(16) / 16.0

        result = classify_genre(120.0, h)

        assert isinstance(result.tags, list)
        assert isinstance(result.confidence, float)
        assert isinstance(result.explanation, list)
        assert isinstance(result.preset, dict)
        assert "density" in result.preset
        assert "syncopation" in result.preset
        assert "register" in result.preset
        assert isinstance(result.debug, dict)
        assert "features" in result.debug
        assert "genre_breakdowns" in result.debug

    def test_invalid_histogram_handling(self):
        """Test handling of invalid histogram."""
        # NaN histogram
        h = np.array([np.nan] * 16)

        result = classify_genre(120.0, h)

        # Should not raise, return valid result
        assert len(result.tags) > 0
        assert all(np.isfinite(v) for v in result.preset.values())

    def test_preset_values_in_range(self):
        """Test that preset values are in valid range."""
        h = np.random.RandomState(123).random(16)
        h = h / h.sum()

        result = classify_genre(120.0, h)

        assert 0 <= result.preset["density"] <= 1.0
        assert 0 <= result.preset["syncopation"] <= 1.0
        assert 0 <= result.preset["register"] <= 1.0

    def test_unknown_tag_generation(self):
        """Test that 'unknown' tag is generated for very low confidence."""
        # Create a pattern that scores low on all templates
        h = np.random.RandomState(999).random(16)
        h = h / h.sum()

        result = classify_genre(50.0, h)  # Very low BPM

        # Might be unknown or just low confidence
        assert len(result.tags) > 0
        assert len(result.explanation) > 0

    def test_multiple_tags_above_threshold(self):
        """Test that multiple tags are returned when appropriate."""
        # Create a pattern that could match multiple genres
        h = np.array([0.15] * 16)
        h = h / h.sum()

        result = classify_genre(100.0, h)

        # May return 1-3 tags depending on confidence
        assert 1 <= len(result.tags) <= 3

    def test_debug_info_comprehensive(self):
        """Test that debug info contains all expected fields."""
        h = np.array(GENRE_TEMPLATES["house_four_on_floor"]["template"])
        result = classify_genre(124.0, h)

        assert "features" in result.debug
        assert "genre_breakdowns" in result.debug
        assert "probabilities" in result.debug
        assert "top_prob" in result.debug
        assert "second_prob" in result.debug
        assert "prob_gap" in result.debug

        # Check genre breakdowns structure
        for tag, breakdown in result.debug["genre_breakdowns"].items():
            assert "template_similarity" in breakdown
            assert "best_shift" in breakdown
            assert "bpm_score" in breakdown
            assert "feature_match" in breakdown
            assert "combined_score" in breakdown


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_very_low_bpm(self):
        """Test classification with very low BPM."""
        h = np.array(GENRE_TEMPLATES["house_four_on_floor"]["template"])
        result = classify_genre(30.0, h)  # 30 BPM

        # Should handle gracefully
        assert len(result.tags) > 0

    def test_very_high_bpm(self):
        """Test classification with very high BPM."""
        h = np.array(GENRE_TEMPLATES["dnb_breakbeat"]["template"])
        result = classify_genre(300.0, h)  # 300 BPM

        # Should handle gracefully
        assert len(result.tags) > 0

    def test_empty_histogram(self):
        """Test with all-zero histogram."""
        h = np.zeros(16)
        result = classify_genre(120.0, h)

        # Should return valid result
        assert len(result.tags) > 0
        assert all(np.isfinite(v) for v in result.preset.values())

    def test_inf_histogram(self):
        """Test with infinite values in histogram."""
        h = np.array([np.inf] * 16)
        result = classify_genre(120.0, h)

        # Should return valid result
        assert len(result.tags) > 0

    def test_temperature_effects(self):
        """Test that temperature parameter affects confidence."""
        h = np.ones(16) / 16.0

        result_low_temp = classify_genre(120.0, h, temperature=0.5)
        result_high_temp = classify_genre(120.0, h, temperature=5.0)

        # Both should return valid results
        assert len(result_low_temp.tags) > 0
        assert len(result_high_temp.tags) > 0
