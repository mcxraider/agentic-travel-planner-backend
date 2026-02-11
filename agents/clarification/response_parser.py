"""
Response parser for the clarification agent.

Handles parsing of LLM responses, including JSON extraction from
various formats (raw JSON, markdown code blocks, etc.).

Score calculation and completion determination are handled by the
scoring module, not extracted from LLM output.
"""

import json
import logging
import re
from typing import Dict, Any, TYPE_CHECKING

from agents.clarification.scoring import (
    calculate_completeness_score,
    should_complete_clarification,
)

if TYPE_CHECKING:
    from agents.clarification.schemas import ClarificationState


logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Raised when response parsing fails."""

    pass


def extract_json_from_response(raw_response: str) -> str:
    """
    Extract JSON content from LLM response.

    Handles multiple formats:
    - Raw JSON
    - JSON in markdown code blocks (```json ... ```)
    - JSON with leading/trailing whitespace

    Args:
        raw_response: Raw LLM response string

    Returns:
        Cleaned JSON string ready for parsing

    Raises:
        ParseError: If no valid JSON structure is found
    """
    content = raw_response.strip()

    # Try to extract from markdown code block
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    match = re.search(code_block_pattern, content)
    if match:
        content = match.group(1).strip()

    # Find JSON object or array boundaries
    if content.startswith("{"):
        # Find matching closing brace
        brace_count = 0
        for i, char in enumerate(content):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    return content[: i + 1]
    elif content.startswith("["):
        # Find matching closing bracket
        bracket_count = 0
        for i, char in enumerate(content):
            if char == "[":
                bracket_count += 1
            elif char == "]":
                bracket_count -= 1
                if bracket_count == 0:
                    return content[: i + 1]

    # If we can't find clear boundaries, return as-is and let JSON parser handle it
    return content


def merge_collected_data(
    existing: Dict[str, Any],
    new_responses: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge new user responses into existing collected data.

    Args:
        existing: Previously collected data
        new_responses: New responses to merge

    Returns:
        Merged dictionary with all collected data
    """
    merged = existing.copy()
    merged.update(new_responses)
    return merged


# =============================================================================
# V2 Response Parsing
# =============================================================================


def parse_clarification_response_v2(raw_response: str) -> Dict[str, Any]:
    """
    Parse a v2 clarification response from the LLM.

    V2 uses a unified JSON structure. Status and score are now determined
    by code, not extracted from LLM output.

    Args:
        raw_response: Raw LLM response string

    Returns:
        Parsed response dictionary with round, questions, state, data

    Raises:
        ParseError: If JSON parsing fails or required keys are missing
    """
    json_str = extract_json_from_response(raw_response)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ParseError(f"Failed to parse v2 response JSON: {e}\nContent: {json_str}")

    # Validate expected structure (status removed - code determines completion)
    required_keys = {"round", "questions", "state", "data"}
    missing_keys = required_keys - set(data.keys())
    if missing_keys:
        raise ParseError(f"V2 response missing required keys: {missing_keys}")

    # Validate state structure (score removed - code calculates it)
    state = data.get("state", {})
    state_required = {"collected"}
    state_missing = state_required - set(state.keys())
    if state_missing:
        raise ParseError(f"V2 state missing required keys: {state_missing}")

    return data


def build_state_update_for_v2_response(
    state: "ClarificationState",
    parsed_response: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a state update dictionary for a v2 response.

    Calculates completeness score and determines completion status using
    code-based logic instead of relying on LLM output.

    Args:
        state: Current clarification state
        parsed_response: Parsed v2 response from LLM

    Returns:
        Dictionary with state updates to apply
    """
    response_data = parsed_response.get("data", {})
    response_state = parsed_response.get("state", {})
    conflicts_detected = response_state.get("conflicts_detected", [])

    # Calculate score using code (replaces LLM-provided score)
    scoring_result = calculate_completeness_score(
        data=response_data,
        work_obligations=state.get("work_obligations"),
        dietary_restrictions=state.get("dietary_restrictions"),
        health_limitations=state.get("health_limitations"),
    )

    # Determine completion status using code (replaces LLM status)
    is_complete, completion_reason = should_complete_clarification(
        scoring_result=scoring_result,
        current_round=state.get("current_round", 1),
        conflicts_detected=conflicts_detected,
    )

    score = scoring_result.score

    # Log scoring breakdown for debugging
    logger.debug(
        "Scoring breakdown - Score: %d, Tier1: %s/%s, Tier2: %s/%s, "
        "Tier3: %s/%s, Tier4: %s/%s, Elevated: %s, Complete: %s (%s)",
        score,
        len(scoring_result.tier1_answered),
        len(scoring_result.tier1_answered) + len(scoring_result.tier1_missing),
        len(scoring_result.tier2_answered),
        len(scoring_result.tier2_answered) + len(scoring_result.tier2_missing),
        len(scoring_result.tier3_answered),
        len(scoring_result.tier3_answered) + len(scoring_result.tier3_missing),
        len(scoring_result.tier4_answered),
        len(scoring_result.tier4_answered) + len(scoring_result.tier4_missing),
        scoring_result.elevated_tier3_fields,
        is_complete,
        completion_reason,
    )

    if is_complete:
        return {
            "clarification_complete": True,
            "current_questions": parsed_response,
            "completeness_score": score,
            "data": response_data,
            "collected_data": response_data,  # Also update collected_data for compatibility
            "messages": [
                {
                    "role": "assistant",
                    "content": "Clarification complete!",
                    "data": response_data,
                }
            ],
        }
    else:
        return {
            "current_round": state["current_round"],
            "current_questions": parsed_response,
            "completeness_score": score,
            "data": response_data,
            "messages": [
                {
                    "role": "assistant",
                    "content": "Questions generated",
                    "questions": parsed_response,
                }
            ],
        }
