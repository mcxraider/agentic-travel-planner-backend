"""
Shared execution helpers for research sub-agent nodes.
"""

import json
import logging
import time
from typing import Any, Callable, Dict, Tuple, Type

from openai import BadRequestError
from pydantic import BaseModel, ValidationError

from agents.research.graph.config import DEFAULT_CONFIG
from agents.shared.llm.client import (
    get_cached_client,
    get_llm_response_with_usage,
    parse_llm_response,
)
from agents.shared.logging import get_or_create_logger


logger = logging.getLogger(__name__)


PromptBuilder = Callable[[Dict[str, Any]], Tuple[str, str]]


def _response_preview(raw_response: str, limit: int = 220) -> str:
    """
    Build a single-line preview of an LLM response for terminal logs.

    Args:
        raw_response: Raw model output string
        limit: Maximum preview length

    Returns:
        Truncated single-line preview
    """
    preview = " ".join(raw_response.split())
    if len(preview) <= limit:
        return preview
    return f"{preview[: limit - 3]}..."


def _should_fallback_to_json_mode(exc: Exception) -> bool:
    """
    Determine whether a structured-output failure should fall back to JSON mode.

    Args:
        exc: Exception raised by the structured parse path

    Returns:
        ``True`` when the caller should retry with ``response_format=json_object``
    """
    if isinstance(exc, AttributeError):
        return True

    if not isinstance(exc, BadRequestError):
        return False

    message = str(exc)
    param = getattr(exc, "param", None)
    return param == "response_format" or "Invalid schema for response_format" in message


def _json_mode_user_prompt(user_prompt: str) -> str:
    """
    Extend a prompt so OpenAI's ``json_object`` mode is explicitly allowed.

    Args:
        user_prompt: Original user prompt

    Returns:
        Prompt text that explicitly requests JSON output
    """
    return (
        f"{user_prompt}\n\n"
        "Return only a valid JSON object that matches the required schema. "
        "Do not include markdown, prose, or code fences."
    )


def _schema_contains_open_object(value: Any) -> bool:
    """
    Recursively detect schema fragments that use open-ended object maps.

    OpenAI structured parsing is stricter than general JSON Schema and rejects
    the ``additionalProperties`` patterns Pydantic emits for ``Dict[...]`` fields.

    Args:
        value: Arbitrary JSON-schema fragment

    Returns:
        ``True`` when the schema contains an open object definition
    """
    if isinstance(value, dict):
        additional_properties = value.get("additionalProperties")
        if additional_properties not in (None, False):
            return True
        return any(_schema_contains_open_object(item) for item in value.values())

    if isinstance(value, list):
        return any(_schema_contains_open_object(item) for item in value)

    return False


def _supports_native_structured_output(response_model: Type[BaseModel]) -> bool:
    """
    Determine whether a response model is safe to send to OpenAI parse().

    Args:
        response_model: Pydantic model used for structured parsing

    Returns:
        ``True`` when the model schema stays within the supported subset
    """
    schema = response_model.model_json_schema()
    return not _schema_contains_open_object(schema)


def call_structured_with_fallback(
    system_prompt: str,
    user_prompt: str,
    response_model: Type[BaseModel],
) -> Tuple[BaseModel, Dict[str, int], str]:
    """
    Call the LLM using structured output, falling back to JSON mode if needed.

    Args:
        system_prompt: Rendered system prompt
        user_prompt: Rendered user prompt
        response_model: Pydantic model for structured parsing

    Returns:
        Tuple of (validated model, usage dict, raw response string)

    Raises:
        ValidationError, json.JSONDecodeError, ValueError: If output cannot be parsed
        APIError, RateLimitError, APITimeoutError, APIConnectionError:
            For transient OpenAI failures
    """
    client = get_cached_client()
    model = DEFAULT_CONFIG.model

    if not _supports_native_structured_output(response_model):
        logger.info(
            "Structured parse skipped for %s due to unsupported schema; using JSON mode",
            response_model.__name__,
        )
        raw_response, usage = get_llm_response_with_usage(
            client=client,
            user_prompt=_json_mode_user_prompt(user_prompt),
            system_prompt=system_prompt,
            model=model,
            response_format={"type": "json_object"},
        )
        payload = json.loads(raw_response)
        result = response_model.model_validate(payload)
        return result, usage, raw_response

    try:
        result, usage = parse_llm_response(
            client=client,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            response_model=response_model,
            model=model,
        )
        return result, usage, result.model_dump_json()
    except (AttributeError, BadRequestError) as exc:
        if not _should_fallback_to_json_mode(exc):
            raise

        logger.warning(
            "Structured parse unavailable for %s, falling back to JSON mode: %s",
            response_model.__name__,
            exc,
        )
        raw_response, usage = get_llm_response_with_usage(
            client=client,
            user_prompt=_json_mode_user_prompt(user_prompt),
            system_prompt=system_prompt,
            model=model,
            response_format={"type": "json_object"},
        )
        payload = json.loads(raw_response)
        result = response_model.model_validate(payload)
        return result, usage, raw_response


def run_research_node(
    state: Dict[str, Any],
    *,
    node_name: str,
    output_key: str,
    prompt_builder: PromptBuilder,
    response_model: Type[BaseModel],
) -> Dict[str, Any]:
    """
    Execute a structured research node with consistent logging and repair behavior.

    Args:
        state: Current research state
        node_name: Graph node name, e.g. ``weather``
        output_key: State key to populate with the node result
        prompt_builder: Callable that returns ``(system_prompt, user_prompt)``
        response_model: Pydantic model for structured output validation

    Returns:
        State update dictionary for the node result or repair routing fields.
    """
    session_id = state.get("session_id") or "unknown"
    debug_logger = get_or_create_logger(session_id)
    model = DEFAULT_CONFIG.model
    log_prefix = f"[session={session_id}] [graph=research] [node={node_name}]"

    system_prompt, user_prompt = prompt_builder(state)
    logger.info(
        "%s Starting node for destination=%s cities=%s",
        log_prefix,
        state.get("destination"),
        state.get("destination_cities") or [],
    )
    logger.info("%s Calling LLM", log_prefix)
    start = time.perf_counter()

    try:
        result, usage, raw_response = call_structured_with_fallback(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
        )
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        logger.warning("%s Parse failure: %s", log_prefix, exc)
        return {
            output_key: None,
            "repair_target": node_name,
            "last_bad_response": getattr(exc, "doc", None) or str(exc),
            "repair_attempt_count": state.get("repair_attempt_count", 0),
            "messages": [
                {
                    "role": "system",
                    "agent": "research",
                    "content": f"{node_name} parse failure: {exc}",
                }
            ],
        }

    duration_ms = (time.perf_counter() - start) * 1000
    debug_logger.log_llm_call(
        round_num=1,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response=raw_response,
        duration_ms=duration_ms,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        model=model,
    )

    logger.info(
        "%s Complete in %.2f ms | tokens in=%s out=%s total=%s | preview=%s",
        log_prefix,
        duration_ms,
        usage["input_tokens"],
        usage["output_tokens"],
        usage["total_tokens"],
        _response_preview(raw_response),
    )
    return {
        output_key: result.model_dump(),
        "repair_target": None,
        "repair_attempt_count": 0,
        "last_bad_response": None,
        "last_repaired_node": None,
        "messages": [
            {
                "role": "system",
                "agent": "research",
                "content": f"{node_name} complete",
            }
        ],
    }
