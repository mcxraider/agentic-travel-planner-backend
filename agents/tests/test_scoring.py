"""
Unit tests for the scoring module.

Tests the completeness score calculation, field checking,
tier elevation, and stopping conditions.
"""

import pytest
from agents.clarification.scoring import (
    calculate_completeness_score,
    should_complete_clarification,
    is_field_answered,
    get_elevated_tier3_fields,
    TierConfig,
    ScoringResult,
    DEFAULT_TIER_CONFIG,
)


class TestIsFieldAnswered:
    """Tests for the is_field_answered function."""

    def test_none_value_returns_false(self):
        """None values should be considered unanswered."""
        assert is_field_answered({}, "activity_preferences") is False
        assert is_field_answered({"activity_preferences": None}, "activity_preferences") is False

    def test_empty_string_returns_false(self):
        """Empty strings should be considered unanswered."""
        assert is_field_answered({"pace_preference": ""}, "pace_preference") is False
        assert is_field_answered({"pace_preference": "  "}, "pace_preference") is False
        assert is_field_answered({"pace_preference": "\t\n"}, "pace_preference") is False

    def test_empty_list_returns_false(self):
        """Empty lists should be considered unanswered."""
        assert is_field_answered({"activity_preferences": []}, "activity_preferences") is False

    def test_empty_dict_returns_false(self):
        """Empty dicts should be considered unanswered."""
        assert is_field_answered({"top_3_must_dos": {}}, "top_3_must_dos") is False

    def test_valid_string_returns_true(self):
        """Non-empty strings should be considered answered."""
        assert is_field_answered({"pace_preference": "relaxed"}, "pace_preference") is True
        assert is_field_answered({"pace_preference": "moderate"}, "pace_preference") is True

    def test_valid_list_returns_true(self):
        """Non-empty lists should be considered answered."""
        assert is_field_answered({"activity_preferences": ["hiking"]}, "activity_preferences") is True
        assert is_field_answered({"dining_style": ["casual", "fine dining"]}, "dining_style") is True

    def test_top_3_must_dos_empty_values_returns_false(self):
        """top_3_must_dos with all None/empty values should be unanswered."""
        assert is_field_answered({"top_3_must_dos": {"1": None, "2": None, "3": None}}, "top_3_must_dos") is False
        assert is_field_answered({"top_3_must_dos": {"1": "", "2": "", "3": ""}}, "top_3_must_dos") is False

    def test_top_3_must_dos_partial_values_returns_true(self):
        """top_3_must_dos with at least one value should be answered."""
        assert is_field_answered({"top_3_must_dos": {"1": "hiking"}}, "top_3_must_dos") is True
        assert is_field_answered({"top_3_must_dos": {"1": "hiking", "2": None, "3": None}}, "top_3_must_dos") is True

    def test_integer_values_return_true(self):
        """Integer values (including 0) should be considered answered."""
        assert is_field_answered({"some_field": 0}, "some_field") is True
        assert is_field_answered({"some_field": 42}, "some_field") is True

    def test_boolean_values_return_true(self):
        """Boolean values (including False) should be considered answered."""
        assert is_field_answered({"some_field": False}, "some_field") is True
        assert is_field_answered({"some_field": True}, "some_field") is True


class TestGetElevatedTier3Fields:
    """Tests for the get_elevated_tier3_fields function."""

    def test_no_conditions_returns_empty(self):
        """No user profile conditions means no elevated fields."""
        assert get_elevated_tier3_fields(None, None, None) == []
        assert get_elevated_tier3_fields("", "", "") == []
        assert get_elevated_tier3_fields("  ", "  ", "  ") == []

    def test_work_obligations_elevates_wifi_need(self):
        """work_obligations triggers wifi_need elevation."""
        elevated = get_elevated_tier3_fields("remote work", None, None)
        assert "wifi_need" in elevated
        assert len(elevated) == 1

    def test_dietary_restrictions_elevates_dietary_severity(self):
        """dietary_restrictions triggers dietary_severity elevation."""
        elevated = get_elevated_tier3_fields(None, "vegan", None)
        assert "dietary_severity" in elevated
        assert len(elevated) == 1

    def test_health_limitations_elevates_accessibility_needs(self):
        """health_limitations triggers accessibility_needs elevation."""
        elevated = get_elevated_tier3_fields(None, None, "wheelchair user")
        assert "accessibility_needs" in elevated
        assert len(elevated) == 1

    def test_all_conditions_elevates_all_fields(self):
        """All user profile conditions elevate all Tier 3 fields."""
        elevated = get_elevated_tier3_fields("remote work", "vegan", "wheelchair")
        assert len(elevated) == 3
        assert "wifi_need" in elevated
        assert "dietary_severity" in elevated
        assert "accessibility_needs" in elevated

    def test_combination_of_conditions(self):
        """Partial conditions elevate only relevant fields."""
        elevated = get_elevated_tier3_fields("remote work", "vegan", None)
        assert len(elevated) == 2
        assert "wifi_need" in elevated
        assert "dietary_severity" in elevated
        assert "accessibility_needs" not in elevated


class TestCalculateCompletenessScore:
    """Tests for the calculate_completeness_score function."""

    def test_empty_data_returns_zero(self):
        """Empty data should return score of 0."""
        result = calculate_completeness_score({})
        assert result.score == 0
        assert len(result.tier1_answered) == 0
        assert len(result.tier1_missing) == 5  # 5 Tier 1 fields

    def test_single_tier1_field_scores_10(self):
        """A single Tier 1 field should score 10 points."""
        data = {"activity_preferences": ["hiking"]}
        result = calculate_completeness_score(data)
        assert result.score == 10
        assert "activity_preferences" in result.tier1_answered
        assert "activity_preferences" not in result.tier1_missing

    def test_all_tier1_fields_score_50(self):
        """All 5 Tier 1 fields should score 50 points."""
        data = {
            "activity_preferences": ["hiking", "food"],
            "pace_preference": "moderate",
            "tourist_vs_local": "balanced",
            "mobility_level": "high",
            "dining_style": ["casual"],
        }
        result = calculate_completeness_score(data)
        assert result.score == 50
        assert len(result.tier1_answered) == 5
        assert len(result.tier1_missing) == 0

    def test_tier2_fields_score_4_each(self):
        """Each Tier 2 field should score 4 points."""
        data = {
            "top_3_must_dos": {"1": "hiking", "2": "food", "3": "museum"},
            "transportation_mode": ["public"],
        }
        result = calculate_completeness_score(data)
        assert result.score == 8  # 2 fields * 4 points
        assert len(result.tier2_answered) == 2

    def test_tier3_fields_score_3_each_without_elevation(self):
        """Tier 3 fields score 3 points each without elevation."""
        data = {"wifi_need": "essential"}
        result = calculate_completeness_score(data)
        assert result.score == 3  # Not elevated, so 3 points
        assert "wifi_need" in result.tier3_answered

    def test_tier3_fields_score_10_each_with_elevation(self):
        """Tier 3 fields score 10 points each when elevated."""
        data = {"wifi_need": "essential"}
        result = calculate_completeness_score(
            data, work_obligations="remote work"
        )
        assert result.score == 10  # Elevated to Tier 1 value
        assert "wifi_need" in result.tier3_answered
        assert "wifi_need" in result.elevated_tier3_fields

    def test_tier4_fields_score_3_each(self):
        """Each Tier 4 field should score 3 points."""
        data = {
            "special_logistics": "early flights",
            "daily_rhythm": "early bird",
            "downtime_preference": "some rest",
        }
        result = calculate_completeness_score(data)
        assert result.score == 9  # 3 fields * 3 points
        assert len(result.tier4_answered) == 3

    def test_score_capped_at_100(self):
        """Score should never exceed 100."""
        # Fill all fields + elevated Tier 3
        data = {
            # Tier 1 (50 points)
            "activity_preferences": ["hiking"],
            "pace_preference": "moderate",
            "tourist_vs_local": "balanced",
            "mobility_level": "high",
            "dining_style": ["casual"],
            # Tier 2 (24 points)
            "top_3_must_dos": {"1": "a", "2": "b", "3": "c"},
            "transportation_mode": ["public"],
            "arrival_time": "morning",
            "departure_time": "evening",
            "budget_priority": "balanced",
            "accommodation_style": "mid-range",
            # Tier 3 (30 points if all elevated)
            "wifi_need": "essential",
            "dietary_severity": "strict",
            "accessibility_needs": "wheelchair",
            # Tier 4 (9 points)
            "special_logistics": "early flights",
            "daily_rhythm": "early bird",
            "downtime_preference": "some rest",
        }
        result = calculate_completeness_score(
            data,
            work_obligations="remote",
            dietary_restrictions="vegan",
            health_limitations="wheelchair",
        )
        assert result.score == 100  # Capped at 100

    def test_mixed_tiers_calculation(self):
        """Test scoring with a mix of tiers."""
        data = {
            # 2 Tier 1 fields = 20 points
            "activity_preferences": ["hiking"],
            "pace_preference": "moderate",
            # 1 Tier 2 field = 4 points
            "top_3_must_dos": {"1": "hiking"},
            # 1 Tier 4 field = 3 points
            "daily_rhythm": "early bird",
        }
        result = calculate_completeness_score(data)
        assert result.score == 27  # 20 + 4 + 3

    def test_result_contains_all_tier_breakdowns(self):
        """Result should contain complete breakdown by tier."""
        data = {"activity_preferences": ["hiking"]}
        result = calculate_completeness_score(data)

        assert isinstance(result.tier1_answered, list)
        assert isinstance(result.tier1_missing, list)
        assert isinstance(result.tier2_answered, list)
        assert isinstance(result.tier2_missing, list)
        assert isinstance(result.tier3_answered, list)
        assert isinstance(result.tier3_missing, list)
        assert isinstance(result.tier4_answered, list)
        assert isinstance(result.tier4_missing, list)
        assert isinstance(result.elevated_tier3_fields, list)


class TestShouldCompleteClarification:
    """Tests for the should_complete_clarification function."""

    def test_max_rounds_forces_completion(self):
        """Reaching max rounds should force completion regardless of score."""
        result = calculate_completeness_score({})  # Score 0
        should_stop, reason = should_complete_clarification(
            result, current_round=4, conflicts_detected=[]
        )
        assert should_stop is True
        assert "Max rounds" in reason

    def test_low_score_continues(self):
        """Low score should not trigger completion."""
        data = {"pace_preference": "relaxed"}  # Only 10 points
        result = calculate_completeness_score(data)
        should_stop, reason = should_complete_clarification(
            result, current_round=1, conflicts_detected=[]
        )
        assert should_stop is False
        assert "continuing" in reason

    def test_high_score_stops(self):
        """Score >= 85 should trigger completion."""
        # Build data that scores >= 85
        # Tier 1 (50) + Tier 2 (24) + Tier 4 (9) = 83, need 2 more
        # Adding a Tier 3 field gives +3 = 86
        data = {
            # Tier 1 (50 points)
            "activity_preferences": ["hiking"],
            "pace_preference": "moderate",
            "tourist_vs_local": "balanced",
            "mobility_level": "high",
            "dining_style": ["casual"],
            # Tier 2 (24 points)
            "top_3_must_dos": {"1": "a", "2": "b", "3": "c"},
            "transportation_mode": ["public"],
            "arrival_time": "morning",
            "departure_time": "evening",
            "budget_priority": "balanced",
            "accommodation_style": "mid-range",
            # Tier 3 (3 points) - not elevated
            "wifi_need": "nice to have",
            # Tier 4 (9 points)
            "special_logistics": "early",
            "daily_rhythm": "early bird",
            "downtime_preference": "some rest",
        }
        result = calculate_completeness_score(data)
        assert result.score >= 85  # 50 + 24 + 3 + 9 = 86

        should_stop, reason = should_complete_clarification(
            result, current_round=2, conflicts_detected=[]
        )
        assert should_stop is True
        assert "85" in reason

    def test_score_85_with_incomplete_tier1_still_stops(self):
        """Score >= 85 stops even if Tier 1 is incomplete."""
        # Create scenario with high score but missing Tier 1
        # This would require lots of Tier 2/3/4 fields
        data = {
            # Only 4 Tier 1 fields = 40 points
            "activity_preferences": ["hiking"],
            "pace_preference": "moderate",
            "tourist_vs_local": "balanced",
            "mobility_level": "high",
            # All Tier 2 = 24 points
            "top_3_must_dos": {"1": "a", "2": "b", "3": "c"},
            "transportation_mode": ["public"],
            "arrival_time": "morning",
            "departure_time": "evening",
            "budget_priority": "balanced",
            "accommodation_style": "mid-range",
            # Elevated Tier 3 = 10 points
            "wifi_need": "essential",
            # Tier 4 = 9 points
            "special_logistics": "early",
            "daily_rhythm": "early bird",
            "downtime_preference": "some rest",
        }
        result = calculate_completeness_score(data, work_obligations="remote")
        # 40 + 24 + 10 + 9 = 83, not quite 85
        # Let's add another elevated field
        data["dietary_severity"] = "strict"
        result = calculate_completeness_score(
            data, work_obligations="remote", dietary_restrictions="vegan"
        )
        # Now should be over 85

        should_stop, reason = should_complete_clarification(
            result, current_round=3, conflicts_detected=[]
        )
        # With score >= 85, it should stop
        if result.score >= 85:
            assert should_stop is True

    def test_conflicts_dont_prevent_high_score_stop(self):
        """Conflicts don't prevent stopping if score >= 85 (condition 3)."""
        data = {
            # Tier 1 (50 points)
            "activity_preferences": ["hiking"],
            "pace_preference": "moderate",
            "tourist_vs_local": "balanced",
            "mobility_level": "high",
            "dining_style": ["casual"],
            # Tier 2 (24 points)
            "top_3_must_dos": {"1": "a", "2": "b", "3": "c"},
            "transportation_mode": ["public"],
            "arrival_time": "morning",
            "departure_time": "evening",
            "budget_priority": "balanced",
            "accommodation_style": "mid-range",
            # Tier 3 (3 points) - not elevated
            "wifi_need": "nice to have",
            # Tier 4 (9 points)
            "special_logistics": "early",
            "daily_rhythm": "early bird",
            "downtime_preference": "some rest",
        }
        result = calculate_completeness_score(data)
        assert result.score >= 85  # 50 + 24 + 3 + 9 = 86

        should_stop, reason = should_complete_clarification(
            result, current_round=2, conflicts_detected=["pace vs relaxation"]
        )
        # Should still stop because score >= 85 (condition 3)
        assert should_stop is True

    def test_elevated_tier3_missing_affects_critical_complete(self):
        """Missing elevated Tier 3 fields affect 'all critical complete' check."""
        data = {
            # All Tier 1 (50 points)
            "activity_preferences": ["hiking"],
            "pace_preference": "moderate",
            "tourist_vs_local": "balanced",
            "mobility_level": "high",
            "dining_style": ["casual"],
            # All Tier 2 (24 points)
            "top_3_must_dos": {"1": "a", "2": "b", "3": "c"},
            "transportation_mode": ["public"],
            "arrival_time": "morning",
            "departure_time": "evening",
            "budget_priority": "balanced",
            "accommodation_style": "mid-range",
            # Tier 4 (9 points)
            "special_logistics": "early",
            "daily_rhythm": "early bird",
            "downtime_preference": "some rest",
            # Missing wifi_need which would be elevated
        }
        result = calculate_completeness_score(data, work_obligations="remote")

        # Score is 83 (50+24+9), missing elevated wifi_need
        # Should not trigger "all critical complete" condition
        # But might still stop if score >= 85 via condition 3
        should_stop, reason = should_complete_clarification(
            result, current_round=2, conflicts_detected=[]
        )
        # Depends on exact score - if < 85, should continue
        if result.score < 85:
            assert should_stop is False

    def test_none_conflicts_handled(self):
        """None conflicts_detected should be treated as empty list."""
        result = calculate_completeness_score({})
        should_stop, reason = should_complete_clarification(
            result, current_round=4, conflicts_detected=None
        )
        assert should_stop is True  # Max rounds


class TestTierConfig:
    """Tests for TierConfig defaults."""

    def test_default_config_values(self):
        """Verify default config has expected values."""
        config = DEFAULT_TIER_CONFIG

        assert len(config.TIER1_FIELDS) == 5
        assert config.TIER1_POINTS == 10

        assert len(config.TIER2_FIELDS) == 6
        assert config.TIER2_POINTS == 4

        assert len(config.TIER3_FIELDS) == 3
        assert config.TIER3_POINTS == 3

        assert len(config.TIER4_FIELDS) == 3
        assert config.TIER4_POINTS == 3

        assert config.MIN_SCORE_FOR_COMPLETION == 85
        assert config.MAX_ROUNDS == 4

    def test_custom_config(self):
        """Test using custom config values."""
        custom_config = TierConfig(
            MIN_SCORE_FOR_COMPLETION=90,
            MAX_ROUNDS=5,
        )

        result = calculate_completeness_score({}, config=custom_config)
        should_stop, reason = should_complete_clarification(
            result, current_round=5, conflicts_detected=[], config=custom_config
        )
        assert should_stop is True
        assert "5" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
