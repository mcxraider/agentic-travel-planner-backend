"""
Prompt builders for the clarification agent.

These functions construct the actual prompts sent to the LLM
based on current state.
"""

import json
from typing import TYPE_CHECKING

from agents.clarification.prompts.templates import (
    SystemPromptConfig,
    SYSTEM_PROMPT_PART_1,
    SYSTEM_PROMPT_PART_2,
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
        return f"\n\nInformation collected so far:\n{json.dumps(collected_data, indent=2)}"
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
