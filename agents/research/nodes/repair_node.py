"""
Repair node for the research graph.
"""

import json
import logging
import time
from typing import Any, Dict, Tuple, Type

from pydantic import BaseModel, ValidationError

from agents.research.graph.config import DEFAULT_CONFIG
from agents.research.nodes.base import call_structured_with_fallback
from agents.research.prompts.builders import (
    build_accommodation_prompts,
    build_activities_prompts,
    build_budget_prompts,
    build_dining_prompts,
    build_highlights_prompts,
    build_overview_prompts,
    build_transport_prompts,
    build_weather_prompts,
)
from agents.research.prompts.templates import (
    AccommodationAreasOutput,
    ActivitiesOutput,
    DestinationOverviewOutput,
    DiningOutput,
    HighlightsOutput,
    InDestinationBudget,
    TransportOutput,
    WeatherInfo,
)
from agents.shared.logging import get_or_create_logger


logger = logging.getLogger(__name__)


_PROMPT_BUILDERS = {
    "weather": build_weather_prompts,
    "overview": build_overview_prompts,
    "budget": build_budget_prompts,
    "accommodation": build_accommodation_prompts,
    "activities": build_activities_prompts,
    "dining": build_dining_prompts,
    "transport": build_transport_prompts,
    "highlights": build_highlights_prompts,
}

_RESPONSE_MODELS: Dict[str, Type[BaseModel]] = {
    "weather": WeatherInfo,
    "overview": DestinationOverviewOutput,
    "budget": InDestinationBudget,
    "accommodation": AccommodationAreasOutput,
    "activities": ActivitiesOutput,
    "dining": DiningOutput,
    "transport": TransportOutput,
    "highlights": HighlightsOutput,
}

_OUTPUT_KEYS = {
    "weather": "weather_output",
    "overview": "destination_overview_output",
    "budget": "budget_analysis_output",
    "accommodation": "accommodation_output",
    "activities": "activities_output",
    "dining": "dining_output",
    "transport": "transportation_output",
    "highlights": "curated_highlights_output",
}


def _build_prompts_for_target(target: str, state: Dict[str, Any]) -> Tuple[str, str]:
    """
    Dispatch to the correct prompt builder based on target node name.

    Args:
        target: Failed node name
        state: Current research state

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    try:
        return _PROMPT_BUILDERS[target](state)
    except KeyError as exc:
        raise ValueError(f"Unknown repair target: {target}") from exc


def _response_model_for_target(target: str) -> Type[BaseModel]:
    """
    Get the structured response model for a failed node.

    Args:
        target: Failed node name

    Returns:
        Pydantic response model class
    """
    try:
        return _RESPONSE_MODELS[target]
    except KeyError as exc:
        raise ValueError(f"Unknown repair target: {target}") from exc


def _output_key_for_target(target: str) -> str:
    """
    Get the state output key for a failed node.

    Args:
        target: Failed node name

    Returns:
        Output key in ``ResearchState``
    """
    try:
        return _OUTPUT_KEYS[target]
    except KeyError as exc:
        raise ValueError(f"Unknown repair target: {target}") from exc


def repair_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attempt to recover from a parse or validation failure in a sub-agent node.

    This node performs up to ``max_repair_attempts`` internal retries before
    giving up and letting graph routing decide whether to skip forward or enter
    degraded mode.

    Args:
        state: Current research state

    Returns:
        State updates for a repaired output or a terminal repair failure.
    """
    target = state.get("repair_target")
    if not target:
        return {
            "errors": ["repair: missing repair_target"],
            "repair_target": None,
            "last_repaired_node": None,
            "messages": [
                {
                    "role": "system",
                    "agent": "research",
                    "content": "repair skipped: missing repair_target",
                }
            ],
        }

    attempt = state.get("repair_attempt_count", 0)
    max_attempts = DEFAULT_CONFIG.max_repair_attempts
    bad_response = state.get("last_bad_response") or ""
    session_id = state.get("session_id") or "unknown"
    debug_logger = get_or_create_logger(session_id)
    model = DEFAULT_CONFIG.model
    log_prefix = (
        f"[session={session_id}] [graph=research] [node=repair] [target={target}]"
    )

    if attempt >= max_attempts:
        logger.error("%s Max repair attempts already reached", log_prefix)
        return {
            "errors": [
                f"{target}: max repair attempts reached, output will be missing"
            ],
            "last_repaired_node": target,
            "repair_target": None,
            "repair_attempt_count": 0,
            "last_bad_response": None,
        }

    system_prompt, original_user_prompt = _build_prompts_for_target(target, state)
    response_model = _response_model_for_target(target)
    output_key = _output_key_for_target(target)
    last_error = bad_response or "Structured output did not match the required schema."

    for current_attempt in range(attempt, max_attempts):
        logger.warning(
            "%s Attempt %s/%s", log_prefix, current_attempt + 1, max_attempts
        )
        repair_user_prompt = (
            f"{original_user_prompt}\n\n"
            f"Your previous response failed schema validation. Here it was:\n\n"
            f"```\n{last_error}\n```\n\n"
            "Regenerate a valid response that strictly matches the required schema."
        )
        start = time.perf_counter()

        try:
            result, usage, raw_response = call_structured_with_fallback(
                system_prompt=system_prompt,
                user_prompt=repair_user_prompt,
                response_model=response_model,
            )
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = getattr(exc, "doc", None) or str(exc)
            logger.warning(
                "%s Repair attempt %s failed: %s", log_prefix, current_attempt + 1, exc
            )
            continue

        duration_ms = (time.perf_counter() - start) * 1000
        debug_logger.log_llm_call(
            round_num=1,
            system_prompt=system_prompt,
            user_prompt=repair_user_prompt,
            response=raw_response,
            duration_ms=duration_ms,
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            model=model,
        )
        logger.info("%s Repair succeeded", log_prefix)
        return {
            output_key: result.model_dump(),
            "last_repaired_node": target,
            "repair_target": None,
            "repair_attempt_count": 0,
            "last_bad_response": None,
            "messages": [
                {
                    "role": "system",
                    "agent": "research",
                    "content": f"repair succeeded for {target}",
                }
            ],
        }

    logger.error(
        "%s Max repair attempts reached, output will remain missing", log_prefix
    )
    return {
        "errors": [f"{target}: max repair attempts reached, output will be missing"],
        "last_repaired_node": target,
        "repair_target": None,
        "repair_attempt_count": 0,
        "last_bad_response": None,
        "messages": [
            {
                "role": "system",
                "agent": "research",
                "content": f"repair failed for {target}",
            }
        ],
    }
