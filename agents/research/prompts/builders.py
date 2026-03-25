"""
Prompt builders for the research agent.

Each builder returns a `(system_prompt, user_prompt)` pair for one research
sub-agent node, using the Stage 1 research state as input.
"""

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from agents.research.prompts.templates import (
    ACCOMMODATION_SYSTEM_PROMPT_TEMPLATE,
    ACTIVITIES_SYSTEM_PROMPT_TEMPLATE,
    BUDGET_SYSTEM_PROMPT_TEMPLATE,
    DINING_SYSTEM_PROMPT_TEMPLATE,
    HIGHLIGHTS_SYSTEM_PROMPT_TEMPLATE,
    OVERVIEW_SYSTEM_PROMPT_TEMPLATE,
    TRANSPORT_SYSTEM_PROMPT_TEMPLATE,
    WEATHER_SYSTEM_PROMPT_TEMPLATE,
    AccommodationPromptConfig,
    ActivitiesPromptConfig,
    BudgetPromptConfig,
    DiningPromptConfig,
    HighlightsPromptConfig,
    OverviewPromptConfig,
    TransportPromptConfig,
    WeatherPromptConfig,
    build_json_context,
)

if TYPE_CHECKING:
    from agents.research.schemas import ResearchState


def _primary_city(state: "ResearchState") -> str:
    """Return the most specific city-like destination value available."""
    cities = state.get("destination_cities") or []
    return cities[0] if cities else state["destination"]


def _must_dos_list(state: "ResearchState") -> List[str]:
    """Normalize ranked must-dos from clarification into an ordered list."""
    must_dos = state.get("top_3_must_dos") or {}
    if isinstance(must_dos, dict):
        return [must_dos[key] for key in sorted(must_dos) if must_dos.get(key)]
    return []


def _budget_tier(state: "ResearchState") -> str:
    """
    Derive a coarse budget tier.

    Prefer a completed budget analysis. Fall back to a simple daily-budget
    heuristic so builders stay usable before the budget node exists.
    """
    budget_output = state.get("budget_analysis_output") or {}
    if budget_output.get("budget_assessment"):
        return str(budget_output["budget_assessment"])

    trip_duration = max(state.get("trip_duration", 1), 1)
    daily_budget = state["budget"] / trip_duration
    if daily_budget < 100:
        return "tight"
    if daily_budget < 250:
        return "comfortable"
    return "generous"


def _json_section(title: str, value: Any) -> str:
    """Render a titled JSON block for the user prompt."""
    return f"{title}:\n{json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True)}"


def _join_sections(sections: List[str]) -> str:
    """Join non-empty prompt sections with blank lines."""
    return "\n\n".join(section for section in sections if section.strip())


def build_weather_prompts(state: "ResearchState") -> Tuple[str, str]:
    """
    Build prompts for the weather research node.

    Args:
        state: Current research state

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    city = _primary_city(state)
    config = WeatherPromptConfig(
        destination=state["destination"],
        city=city,
        start_date=state["start_date"],
        end_date=state["end_date"],
    )
    system_prompt = config.format_prompt(WEATHER_SYSTEM_PROMPT_TEMPLATE)
    user_prompt = _join_sections(
        [
            f"Research weather planning guidance for {city}, {state['destination']}.",
            f"Trip dates: {state['start_date']} to {state['end_date']}.",
            "Use seasonal expectations appropriate for trip planning rather than exact forecasts.",
        ]
    )
    return system_prompt, user_prompt


def build_overview_prompts(state: "ResearchState") -> Tuple[str, str]:
    """
    Build prompts for the destination overview node.

    Args:
        state: Current research state

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    city = _primary_city(state)
    config = OverviewPromptConfig(
        destination=state["destination"],
        city=city,
        trip_duration=state["trip_duration"],
        travel_party=state["travel_party"],
    )
    system_prompt = config.format_prompt(OVERVIEW_SYSTEM_PROMPT_TEMPLATE)
    user_prompt = _join_sections(
        [
            f"Summarize {city} for a {state['trip_duration']}-day {state['travel_party']} trip.",
            _json_section(
                "Traveler preferences",
                {
                    "activity_preferences": state.get("activity_preferences"),
                    "pace_preference": state.get("pace_preference"),
                    "tourist_vs_local": state.get("tourist_vs_local"),
                },
            ),
        ]
    )
    return system_prompt, user_prompt


def build_budget_prompts(state: "ResearchState") -> Tuple[str, str]:
    """
    Build prompts for the budget analysis node.

    Args:
        state: Current research state

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    city = _primary_city(state)
    config = BudgetPromptConfig(
        destination=state["destination"],
        city=city,
        budget=state["budget"],
        currency=state["currency"],
        trip_duration=state["trip_duration"],
        travel_party=state["travel_party"],
        budget_priority=state.get("budget_priority"),
    )
    system_prompt = config.format_prompt(BUDGET_SYSTEM_PROMPT_TEMPLATE)
    user_prompt = _join_sections(
        [
            "Allocate the full budget across accommodation, food, activities, and local transport.",
            _json_section(
                "Budget inputs",
                {
                    "destination": state["destination"],
                    "city": city,
                    "trip_duration": state["trip_duration"],
                    "budget": state["budget"],
                    "currency": state["currency"],
                    "travel_party": state["travel_party"],
                    "budget_priority": state.get("budget_priority"),
                },
            ),
        ]
    )
    return system_prompt, user_prompt


def build_accommodation_prompts(state: "ResearchState") -> Tuple[str, str]:
    """
    Build prompts for the accommodation recommendation node.

    Args:
        state: Current research state

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    city = _primary_city(state)
    config = AccommodationPromptConfig(
        destination=state["destination"],
        city=city,
        accommodation_style=state.get("accommodation_style"),
        mobility_level=state.get("mobility_level"),
        budget_tier=_budget_tier(state),
        travel_party=state["travel_party"],
    )
    system_prompt = config.format_prompt(ACCOMMODATION_SYSTEM_PROMPT_TEMPLATE)
    user_prompt = _join_sections(
        [
            f"Recommend the best areas to stay in {city}.",
            _json_section(
                "Context",
                {
                    "destination_overview_output": state.get(
                        "destination_overview_output"
                    ),
                    "budget_analysis_output": state.get("budget_analysis_output"),
                    "accommodation_style": state.get("accommodation_style"),
                    "mobility_level": state.get("mobility_level"),
                },
            ),
        ]
    )
    return system_prompt, user_prompt


def build_activities_prompts(state: "ResearchState") -> Tuple[str, str]:
    """
    Build prompts for the activities recommendation node.

    Args:
        state: Current research state

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    city = _primary_city(state)
    config = ActivitiesPromptConfig(
        destination=state["destination"],
        city=city,
        activity_preferences=state.get("activity_preferences"),
        tourist_vs_local=state.get("tourist_vs_local"),
        pace_preference=state.get("pace_preference"),
        mobility_level=state.get("mobility_level"),
        must_dos=_must_dos_list(state),
    )
    system_prompt = config.format_prompt(ACTIVITIES_SYSTEM_PROMPT_TEMPLATE)
    user_prompt = _join_sections(
        [
            f"Recommend activities in {city} aligned with the traveler profile.",
            _json_section(
                "Context",
                {
                    "destination_overview_output": state.get(
                        "destination_overview_output"
                    ),
                    "weather_output": state.get("weather_output"),
                    "top_3_must_dos": state.get("top_3_must_dos"),
                    "activity_preferences": state.get("activity_preferences"),
                    "tourist_vs_local": state.get("tourist_vs_local"),
                    "pace_preference": state.get("pace_preference"),
                    "mobility_level": state.get("mobility_level"),
                },
            ),
        ]
    )
    return system_prompt, user_prompt


def build_dining_prompts(state: "ResearchState") -> Tuple[str, str]:
    """
    Build prompts for the dining recommendation node.

    Args:
        state: Current research state

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    city = _primary_city(state)
    config = DiningPromptConfig(
        destination=state["destination"],
        city=city,
        dining_style=state.get("dining_style"),
        dietary_restrictions=state.get("dietary_restrictions"),
        budget_tier=_budget_tier(state),
        travel_party=state["travel_party"],
    )
    system_prompt = config.format_prompt(DINING_SYSTEM_PROMPT_TEMPLATE)
    user_prompt = _join_sections(
        [
            f"Recommend dining options in {city} suitable for this traveler.",
            _json_section(
                "Context",
                {
                    "destination_overview_output": state.get(
                        "destination_overview_output"
                    ),
                    "budget_analysis_output": state.get("budget_analysis_output"),
                    "dining_style": state.get("dining_style"),
                    "dietary_restrictions": state.get("dietary_restrictions"),
                    "travel_party": state["travel_party"],
                },
            ),
        ]
    )
    return system_prompt, user_prompt


def build_transport_prompts(state: "ResearchState") -> Tuple[str, str]:
    """
    Build prompts for the local transport node.

    Args:
        state: Current research state

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    city = _primary_city(state)
    config = TransportPromptConfig(
        destination=state["destination"],
        city=city,
        mobility_level=state.get("mobility_level"),
        budget_tier=_budget_tier(state),
        trip_duration=state["trip_duration"],
    )
    system_prompt = config.format_prompt(TRANSPORT_SYSTEM_PROMPT_TEMPLATE)
    user_prompt = _join_sections(
        [
            f"Recommend local transport options for getting around {city}.",
            _json_section(
                "Context",
                {
                    "destination_overview_output": state.get(
                        "destination_overview_output"
                    ),
                    "budget_analysis_output": state.get("budget_analysis_output"),
                    "mobility_level": state.get("mobility_level"),
                    "trip_duration": state["trip_duration"],
                },
            ),
        ]
    )
    return system_prompt, user_prompt


def build_highlights_prompts(state: "ResearchState") -> Tuple[str, str]:
    """
    Build prompts for the curated highlights synthesis node.

    Args:
        state: Current research state

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    city = _primary_city(state)
    activities_json = build_json_context(
        state.get("activities_output") or {"items": []}
    )
    dining_json = build_json_context(state.get("dining_output") or {"items": []})
    overview_output = state.get("destination_overview_output") or {}
    config = HighlightsPromptConfig(
        destination=state["destination"],
        city=city,
        must_dos=_must_dos_list(state),
        activity_preferences=state.get("activity_preferences"),
        activities_json=activities_json,
        dining_json=dining_json,
        overview=overview_output.get("overview"),
    )
    system_prompt = config.format_prompt(HIGHLIGHTS_SYSTEM_PROMPT_TEMPLATE)
    user_prompt = _join_sections(
        [
            f"Synthesize the highest-value highlights for {city}.",
            _json_section(
                "Traveler context",
                {
                    "top_3_must_dos": state.get("top_3_must_dos"),
                    "activity_preferences": state.get("activity_preferences"),
                    "tourist_vs_local": state.get("tourist_vs_local"),
                },
            ),
            f"Activities JSON:\n{activities_json}",
            f"Dining JSON:\n{dining_json}",
        ]
    )
    return system_prompt, user_prompt


__all__ = [
    "build_weather_prompts",
    "build_overview_prompts",
    "build_budget_prompts",
    "build_accommodation_prompts",
    "build_activities_prompts",
    "build_dining_prompts",
    "build_transport_prompts",
    "build_highlights_prompts",
]
