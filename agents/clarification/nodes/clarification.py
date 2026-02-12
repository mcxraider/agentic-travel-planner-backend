"""
Clarification node for the LangGraph workflow.

This is the main node that calls the LLM to generate questions
or complete the clarification process.
"""

import logging
import time
from typing import Dict, Any

from agents.clarification.schemas import ClarificationState
from agents.clarification.prompts.builders import (
    build_system_prompt_v2,
    build_user_prompt_v2,
)
from agents.clarification.response_parser import (
    parse_clarification_response_v2,
    build_state_update_for_v2_response,
    ParseError,
)
from agents.shared.llm.client import get_cached_client, get_llm_response_with_usage
from agents.shared.logging.debug_logger import get_or_create_logger
from agents.shared.cache import load_system_prompt


logger = logging.getLogger(__name__)


# Default model for clarification
DEFAULT_MODEL = "gpt-4.1-mini"


def clarification_node(state: ClarificationState) -> Dict[str, Any]:
    """
    Main clarification node that generates questions or completes clarification.

    This is a pure function that:
    1. Builds prompts from current state
    2. Calls the LLM
    3. Parses the response
    4. Returns state updates

    Args:
        state: Current clarification state

    Returns:
        Dictionary with state updates to apply

    Raises:
        Exception: If LLM call or parsing fails after all retries
    """
    session_id = state.get("session_id", "unknown")
    current_round = state.get("current_round", 0)
    score = state.get("completeness_score", 0)
    _log = f"[session={session_id}] [graph=clarification] [node=clarification] "

    logger.info(
        f"{_log}Entering node | round={current_round}, score={score}/100, "
        f"destination={state.get('destination', 'N/A')}"
    )

    try:
        client = get_cached_client()

        # Load cached system prompt (built once at session start for OpenAI caching)
        system_prompt = load_system_prompt(session_id) if session_id != "unknown" else None

        # Fallback: rebuild if cache miss (defensive)
        if system_prompt is None:
            system_prompt = build_system_prompt_v2(state)
            logger.warning(f"{_log}Cache miss - rebuilt system prompt")

        # Build user prompt (changes each round with new data)
        user_prompt = build_user_prompt_v2(state)

        # Get debug logger from registry if session_id is available
        debug_logger = get_or_create_logger(session_id) if session_id != "unknown" else None

        # Log collected fields so far
        filled_fields = [k for k, v in state.get("data", {}).items() if v is not None]
        logger.info(
            f"{_log}Calling LLM | model={DEFAULT_MODEL}, "
            f"filled_fields={len(filled_fields)}/{len(state.get('data', {}))}"
        )
        logger.debug(f"{_log}Filled fields: {filled_fields}")

        # Call LLM with timing
        start_time = time.perf_counter()
        llm_response, usage = get_llm_response_with_usage(
            client, user_prompt, system_prompt, model=DEFAULT_MODEL
        )
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log to debug file
        if debug_logger:
            debug_logger.log_llm_call(
                round_num=current_round,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=llm_response,
                duration_ms=duration_ms,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                model=DEFAULT_MODEL,
            )

        logger.info(
            f"{_log}LLM responded | duration={duration_ms:.0f}ms, "
            f"tokens_in={usage['input_tokens']}, tokens_out={usage['output_tokens']}"
        )

        # Parse v2 response (unified format for both in-progress and complete)
        parsed_response = parse_clarification_response_v2(llm_response)

        # Build state update using v2 handler
        result = build_state_update_for_v2_response(state, parsed_response)

        # Log outcome
        is_complete = result.get('clarification_complete', False)
        new_score = result.get('completeness_score', 0)
        num_questions = len(result.get('current_questions', {}).get('questions', []))
        logger.info(
            f"{_log}Node finished | complete={is_complete}, score={new_score}/100, "
            f"questions_generated={num_questions}"
        )

        if is_complete:
            logger.info(f"{_log}Clarification COMPLETE - will route to output node")
        else:
            logger.info(
                f"{_log}Clarification IN PROGRESS - will pause for human feedback "
                f"(interrupt_after=clarification)"
            )

        return result

    except ParseError as e:
        logger.error(f"{_log}Parse error: {e}")
        raise

    except Exception as e:
        logger.exception(f"{_log}Unhandled error: {e}")
        raise
