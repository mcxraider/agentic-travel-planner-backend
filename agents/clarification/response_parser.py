"""
Response parser for the clarification agent.

Handles parsing of LLM responses, including JSON extraction from
various formats (raw JSON, markdown code blocks, etc.).
"""

import json
import re
from typing import Dict, Any, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agents.clarification.schemas import ClarificationState


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


def is_clarification_complete(raw_response: str) -> bool:
    """
    Check if the LLM response indicates clarification is complete.

    Args:
        raw_response: Raw LLM response string

    Returns:
        True if response starts with "Clarification Done"
    """
    return raw_response.strip().startswith("Clarification Done")


def parse_final_data(raw_response: str) -> Dict[str, Any]:
    """
    Parse the final collected data from a completion response.

    Args:
        raw_response: Raw LLM response starting with "Clarification Done"

    Returns:
        Parsed dictionary of collected user preferences

    Raises:
        ParseError: If JSON parsing fails
    """
    # Remove the "Clarification Done" prefix
    content = raw_response.replace("Clarification Done", "").strip()

    # Extract and parse JSON
    json_str = extract_json_from_response(content)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ParseError(f"Failed to parse final data JSON: {e}\nContent: {json_str}")


def parse_questions_response(raw_response: str) -> Dict[str, Any]:
    """
    Parse a questions response from the LLM.

    Args:
        raw_response: Raw LLM response containing questions JSON

    Returns:
        Parsed questions dictionary with status, round, questions, and state

    Raises:
        ParseError: If JSON parsing fails
    """
    json_str = extract_json_from_response(raw_response)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ParseError(f"Failed to parse questions JSON: {e}\nContent: {json_str}")

    # Validate expected structure
    required_keys = {"status", "round", "questions", "state"}
    missing_keys = required_keys - set(data.keys())
    if missing_keys:
        raise ParseError(f"Questions response missing required keys: {missing_keys}")

    return data


def parse_clarification_response(
    raw_response: str,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Parse an LLM response and determine if clarification is complete.

    Args:
        raw_response: Raw LLM response string

    Returns:
        Tuple of (is_complete, parsed_data)
        - If complete: (True, final_collected_data_dict)
        - If not complete: (False, questions_response_dict)

    Raises:
        ParseError: If parsing fails
    """
    if is_clarification_complete(raw_response):
        final_data = parse_final_data(raw_response)
        return (True, final_data)
    else:
        questions_data = parse_questions_response(raw_response)
        return (False, questions_data)


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


def build_state_update_for_questions(
    state: "ClarificationState",
    questions_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a state update dictionary for a questions response.

    Args:
        state: Current clarification state
        questions_data: Parsed questions response

    Returns:
        Dictionary with state updates to apply
    """
    return {
        "current_round": state["current_round"],
        "current_questions": questions_data,
        "completeness_score": questions_data["state"]["completeness_score"],
        "messages": [
            {
                "role": "assistant",
                "content": "Questions generated",
                "questions": questions_data,
            }
        ],
    }


def build_state_update_for_completion(
    final_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a state update dictionary for a completion response.

    Args:
        final_data: Final collected data from LLM

    Returns:
        Dictionary with state updates to apply
    """
    return {
        "clarification_complete": True,
        "collected_data": final_data,
        "completeness_score": 100,
        "messages": [
            {
                "role": "assistant",
                "content": "Clarification complete!",
                "data": final_data,
            }
        ],
    }
