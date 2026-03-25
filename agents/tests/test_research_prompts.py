"""
Tests for research prompt builders and contract-facing prompt semantics.
"""

from pydantic import ValidationError

from agents.research.prompts.builders import (
    build_activities_prompts,
    build_budget_prompts,
    build_dining_prompts,
    build_highlights_prompts,
    build_weather_prompts,
)
from agents.shared.contracts.research_output_v2 import Activity


def _base_state():
    """Create a stable research state fixture for prompt-builder tests."""
    return {
        "destination": "Japan",
        "destination_cities": ["Tokyo"],
        "start_date": "2026-04-10",
        "end_date": "2026-04-17",
        "trip_duration": 7,
        "budget": 2000.0,
        "currency": "USD",
        "travel_party": "couple",
        "activity_preferences": ["temples", "food tours", "street markets"],
        "pace_preference": "moderate",
        "dining_style": ["local street food", "sit-down restaurants"],
        "accommodation_style": ["boutique hotel", "central location"],
        "mobility_level": "full",
        "dietary_restrictions": None,
        "top_3_must_dos": {
            "1": "Tsukiji Outer Market",
            "2": "teamLab Planets TOKYO",
            "3": "Shibuya Scramble Crossing",
        },
        "budget_priority": "experiences_over_comfort",
        "tourist_vs_local": "mix",
        "clarification_output": None,
        "weather_output": None,
        "destination_overview_output": {
            "city_name": "Tokyo",
            "country": "Japan",
            "overview": "Dense neighborhoods, major rail coverage, and high variety.",
            "recommended_days": 6,
        },
        "budget_analysis_output": {
            "total_available_usd": 2000.0,
            "trip_duration_days": 7,
            "daily_budget_usd": 285.71,
            "breakdown": {
                "accommodation": 800.0,
                "food": 500.0,
                "activities": 500.0,
                "local_transport": 200.0,
            },
            "budget_assessment": "comfortable",
            "budget_tips": ["Use a transit card for local trains and metro."],
        },
        "accommodation_output": None,
        "activities_output": {
            "items": [
                {
                    "name": "Senso-ji Temple",
                    "category": "culture",
                    "neighborhood": "Asakusa",
                    "description": "Historic temple complex with surrounding market streets.",
                    "estimated_duration_hours": 2.0,
                    "estimated_cost_usd": 0.0,
                    "travel_time_from_centre_mins": 25,
                    "best_time_to_visit": "early morning",
                    "booking_required": False,
                    "tags": ["temples", "history"],
                }
            ]
        },
        "dining_output": {
            "items": [
                {
                    "name": "Tsukiji Outer Market",
                    "cuisine_type": "seafood market",
                    "description": "Busy market known for fresh seafood stalls.",
                    "price_tier": "mid-range",
                    "estimated_cost_per_person_usd": 20.0,
                    "must_try_dishes": ["otoro sushi"],
                    "neighborhood": "Tsukiji",
                    "best_for": "breakfast",
                }
            ]
        },
        "transportation_output": None,
        "curated_highlights_output": None,
        "research_output": None,
        "research_complete": False,
        "repair_target": None,
        "repair_attempt_count": 0,
        "last_bad_response": None,
        "last_repaired_node": None,
        "errors": [],
        "messages": [],
        "session_id": "prompt-test-001",
    }


def test_build_budget_prompts_include_destination_and_city_context():
    """Budget prompts should include destination purchasing-power context."""
    system_prompt, user_prompt = build_budget_prompts(_base_state())

    assert "The traveler is going to Tokyo, Japan." in system_prompt
    assert "Account for destination purchasing power" in system_prompt
    assert '"city": "Tokyo"' in user_prompt
    assert '"destination": "Japan"' in user_prompt


def test_build_activities_prompts_include_neighborhood_and_travel_time_requirements():
    """Activities prompt should instruct the model to populate planner-grouping fields."""
    system_prompt, _ = build_activities_prompts(_base_state())

    assert "Assign each activity a neighborhood or district name" in system_prompt
    assert "travel_time_from_centre_mins" in system_prompt
    assert "central accommodation zone in Tokyo" in system_prompt


def test_build_highlights_prompts_include_linking_and_mix_constraints():
    """Highlights prompt should anchor count, linking, and category requirements."""
    system_prompt, user_prompt = build_highlights_prompts(_base_state())

    assert "Return between 6 and 10 highlights." in system_prompt
    assert "exactly match the source item name" in system_prompt
    assert "Include at least 2 dining highlights." in system_prompt
    assert "Include at least 1 hidden_gem highlight." in system_prompt
    assert (
        "category must be exactly one of: experience, dining, hidden_gem."
        in system_prompt
    )
    assert "Activities JSON:" in user_prompt
    assert "Dining JSON:" in user_prompt


def test_build_dining_prompts_render_no_dietary_restrictions_sentence():
    """Dining prompt should use a sentence-style absence marker instead of a raw placeholder."""
    system_prompt, _ = build_dining_prompts(_base_state())

    assert "No dietary restrictions." in system_prompt
    assert "None specified" not in system_prompt


def test_build_weather_prompts_include_season_derivation_requirements():
    """Weather prompt should explicitly standardize season derivation."""
    system_prompt, user_prompt = build_weather_prompts(_base_state())

    assert (
        "Derive the season from the travel window for the correct hemisphere."
        in system_prompt
    )
    assert (
        "Output season as exactly one of: spring, summer, autumn, winter."
        in system_prompt
    )
    assert "Trip dates: 2026-04-10 to 2026-04-17." in user_prompt


def test_activity_validation_accepts_neighborhood_without_travel_time():
    """Activity should validate when the required neighborhood is present."""
    result = Activity.model_validate(
        {
            "name": "Meiji Shrine",
            "category": "culture",
            "neighborhood": "Harajuku",
            "description": "Forest-lined shrine grounds near Yoyogi Park.",
            "estimated_duration_hours": 1.5,
            "estimated_cost_usd": 0.0,
            "best_time_to_visit": "morning",
            "booking_required": False,
            "tags": ["shrines", "walking"],
        }
    )

    assert result.neighborhood == "Harajuku"
    assert result.travel_time_from_centre_mins is None


def test_activity_validation_accepts_neighborhood_with_travel_time():
    """Activity should validate when both planner-grouping fields are present."""
    result = Activity.model_validate(
        {
            "name": "teamLab Planets TOKYO",
            "category": "art",
            "neighborhood": "Toyosu",
            "description": "Immersive digital art museum experience.",
            "estimated_duration_hours": 2.0,
            "estimated_cost_usd": 28.0,
            "travel_time_from_centre_mins": 30,
            "best_time_to_visit": "late afternoon",
            "booking_required": True,
            "tags": ["immersive", "art"],
        }
    )

    assert result.neighborhood == "Toyosu"
    assert result.travel_time_from_centre_mins == 30


def test_activity_validation_requires_neighborhood():
    """Activity should reject payloads that omit the required neighborhood field."""
    try:
        Activity.model_validate(
            {
                "name": "Tokyo National Museum",
                "category": "museum",
                "description": "Major collection of Japanese art and artifacts.",
                "estimated_duration_hours": 3.0,
                "estimated_cost_usd": 8.0,
                "best_time_to_visit": "morning",
                "booking_required": False,
                "tags": ["museum", "history"],
            }
        )
    except ValidationError as exc:
        assert "neighborhood" in str(exc)
    else:
        raise AssertionError("Expected neighborhood to be required")
