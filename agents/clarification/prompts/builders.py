"""
Prompt builders for the clarification agent.

These functions construct the actual prompts sent to the LLM
based on current state.
"""

import json
from typing import TYPE_CHECKING, Dict, Any, List, Optional

from agents.clarification.prompts.templates import (
    SystemPromptConfig,
    SystemPromptConfigV2,
    SYSTEM_PROMPT_PART_1,
    SYSTEM_PROMPT_PART_2,
    V2_SYSTEM_PROMPT_TEMPLATE,
)

if TYPE_CHECKING:
    from agents.clarification.schemas import ClarificationState


def build_user_context(state: "ClarificationState") -> str:
    """
    Build the user context section of the system prompt.

    Args:
        state: Current clarification state

    Returns:
        Formatted string with user and trip context
    """
    config = SystemPromptConfig(
        user_name=state["user_name"],
        citizenship=state["citizenship"],
        health_limitations=state.get("health_limitations"),
        work_obligations=state.get("work_obligations"),
        dietary_restrictions=state.get("dietary_restrictions"),
        specific_interests=state.get("specific_interests"),
        destination=state["destination"],
        start_date=state["start_date"],
        end_date=state["end_date"],
        trip_duration=state["trip_duration"],
        budget=state["budget"],
        currency=state["currency"],
        travel_party=state["travel_party"],
        budget_scope=state["budget_scope"],
    )
    return config.format_user_context()


def build_system_prompt(state: "ClarificationState") -> str:
    """
    Build the complete system prompt for the clarification agent.

    Combines the static prompt parts with dynamic user context.

    Args:
        state: Current clarification state

    Returns:
        Complete system prompt string
    """
    user_context = build_user_context(state)
    return SYSTEM_PROMPT_PART_1 + user_context + SYSTEM_PROMPT_PART_2


def build_collected_data_text(state: "ClarificationState") -> str:
    """
    Build text representation of collected data so far.

    Args:
        state: Current clarification state

    Returns:
        Formatted string with collected data, or empty string if none
    """
    collected_data = state.get("collected_data", {})
    if collected_data:
        return (
            f"\n\nInformation collected so far:\n{json.dumps(collected_data, indent=2)}"
        )
    return ""


def build_user_response_text(state: "ClarificationState") -> str:
    """
    Build text representation of user's previous response.

    Args:
        state: Current clarification state

    Returns:
        Formatted string with user response, or empty string if round 1
    """
    user_response = state.get("user_response")
    current_round = state["current_round"]

    if user_response and current_round > 1:
        return f"\n\nUser's responses from Round {current_round - 1}:\n{json.dumps(user_response, indent=2)}"
    return ""


def build_user_prompt(state: "ClarificationState") -> str:
    """
    Build the user prompt for the clarification agent.

    Combines collected data, previous responses, and round instruction.

    Args:
        state: Current clarification state

    Returns:
        Complete user prompt string
    """
    collected_data_text = build_collected_data_text(state)
    user_response_text = build_user_response_text(state)

    return f"""{collected_data_text}{user_response_text}
This is Round {state['current_round']}. Generate questions or complete clarification as appropriate."""


# =============================================================================
# V2 Prompt Builders
# =============================================================================


def get_initial_data_object() -> Dict[str, Any]:
    """
    Get the initial data object with all v2 fields set to null.

    Returns:
        Dictionary with all v2 data fields initialized to null
    """
    return {
        # Tier 1: Critical
        "activity_preferences": None,
        "pace_preference": None,
        "tourist_vs_local": None,
        "mobility_level": None,
        "dining_style": None,
        # Tier 2: Planning Essentials
        "top_3_must_dos": None,
        "transportation_mode": None,
        "arrival_time": None,
        "departure_time": None,
        "budget_priority": None,
        "accommodation_style": None,
        # Tier 3: Conditional Critical
        "wifi_need": None,
        "dietary_severity": None,
        "accessibility_needs": None,
        # Tier 4: Optimization
        "daily_rhythm": None,
        "downtime_preference": None,
        # Meta fields
        "_conflicts_resolved": [],
        "_warnings": [],
    }


def build_system_prompt_v2(state: "ClarificationState") -> str:
    """
    Build the complete system prompt for the v2 clarification agent.

    Uses the v2 template with dynamic context.

    Args:
        state: Current clarification state

    Returns:
        Complete system prompt string
    """
    # Format destination_cities as comma-separated string
    cities = state.get("destination_cities")
    cities_str = ", ".join(cities) if cities else None

    config = SystemPromptConfigV2(
        user_name=state["user_name"],
        citizenship=state["citizenship"],
        health_limitations=state.get("health_limitations"),
        work_obligations=state.get("work_obligations"),
        dietary_restrictions=state.get("dietary_restrictions"),
        specific_interests=state.get("specific_interests"),
        destination_country=state["destination"],
        destination_cities=cities_str,
        start_date=state["start_date"],
        end_date=state["end_date"],
        trip_duration=state["trip_duration"],
        budget_amount=state["budget"],
        currency=state["currency"],
        party_composition=state["travel_party"],
        budget_scope=state["budget_scope"],
    )

    return config.format_prompt(V2_SYSTEM_PROMPT_TEMPLATE)


def build_user_prompt_v2(state: "ClarificationState") -> str:
    """
    Build the user prompt for the v2 clarification agent.

    Includes cumulative data object (JSON) for LLM context,
    user's latest responses (for rounds 2+), and round instruction.

    Args:
        state: Current clarification state

    Returns:
        Complete user prompt string
    """
    parts = []

    # Include cumulative data object
    data = state.get("data") or get_initial_data_object()
    parts.append(f"Current collected data:\n{json.dumps(data, indent=2)}")

    # Include user's latest responses (for rounds 2+)
    user_response = state.get("user_response")
    current_round = state["current_round"]

    if user_response and current_round > 1:
        parts.append(
            f"\nUser's responses from Round {current_round - 1}:\n{json.dumps(user_response, indent=2)}"
        )

    # Round instruction
    parts.append(
        f"\nThis is Round {current_round}. Generate questions or complete clarification."
    )

    return "\n".join(parts)


def merge_user_responses_into_data(
    current_data: Optional[Dict[str, Any]],
    user_responses: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge user responses into the cumulative data object.

    Handles special cases like:
    - top_3_must_dos: list → ranked object conversion
    - Arrays vs single values

    Args:
        current_data: Existing data object (or None for initial)
        user_responses: New responses from user

    Returns:
        Merged data dictionary
    """
    # Start with current data or initial empty object
    merged = (current_data or get_initial_data_object()).copy()

    for field, value in user_responses.items():
        if value is None:
            continue

        # Handle top_3_must_dos: convert list to ranked object
        if field == "top_3_must_dos":
            if isinstance(value, list):
                # Convert list ["A", "B", "C"] to {"1": "A", "2": "B", "3": "C"}
                ranked = {}
                for i, item in enumerate(value[:3], start=1):
                    ranked[str(i)] = item
                merged[field] = ranked
            elif isinstance(value, dict):
                # Already in correct format
                merged[field] = value
        else:
            # Direct assignment for other fields
            merged[field] = value

    return merged
