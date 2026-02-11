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


logger = logging.getLogger("agents.clarification")
logger.setLevel(logging.INFO)  # log INFO and above

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


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
    try:
        client = get_cached_client()

        # Load cached system prompt (built once at session start for OpenAI caching)
        session_id = state.get("session_id")
        system_prompt = load_system_prompt(session_id) if session_id else None

        # Fallback: rebuild if cache miss (defensive)
        if system_prompt is None:
            system_prompt = build_system_prompt_v2(state)
            print("CACHE MISS: Rebuilt system prompt")
            logger.warning(
                f"Cache miss for session {session_id}, rebuilt system prompt"
            )

        # Build user prompt (changes each round with new data)
        user_prompt = build_user_prompt_v2(state)

        # Get debug logger from registry if session_id is available
        debug_logger = get_or_create_logger(session_id) if session_id else None

        # Log the call
        logger.info(
            f"Round {state['current_round']} - Calling LLM (v2)",
            extra={
                "round": state["current_round"],
                "data_keys": list(
                    k for k, v in state.get("data", {}).items() if v is not None
                ),
                "completeness_score": state.get("completeness_score", 0),
            },
        )

        # Debug output (for development)
        print("\n" + "=" * 80)
        print(f"🤖 Round {state['current_round']} - Calling LLM (v2)")
        print("=" * 80)

        # Call LLM with timing
        start_time = time.perf_counter()
        llm_response, usage = get_llm_response_with_usage(
            client, user_prompt, system_prompt, model=DEFAULT_MODEL
        )
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log to debug file
        if debug_logger:
            debug_logger.log_llm_call(
                round_num=state["current_round"],
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=llm_response,
                duration_ms=duration_ms,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                model=DEFAULT_MODEL,
            )

        # Print token usage to console
        print(
            f"\n📈 Token Usage: {usage['input_tokens']} in / {usage['output_tokens']} out"
        )
        print(f"⏱️  LLM Duration: {duration_ms:.2f}ms")

        # Parse v2 response (unified format for both in-progress and complete)
        parsed_response = parse_clarification_response_v2(llm_response)

        # Build state update using v2 handler
        result = build_state_update_for_v2_response(state, parsed_response)

        # Log completion
        is_complete = result.get('clarification_complete', False)
        status = "complete" if is_complete else "in_progress"
        print(
            f"✅ Round {state['current_round']} completed - "
            f"Status: {status} - "
            f"Score: {result.get('completeness_score', 0)}/100"
        )

        return result

    except ParseError as e:
        logger.error(f"Parse error in clarification_node: {e}")
        print(f"❌ Parse error in clarification_node: {e}")
        raise

    except Exception as e:
        logger.error(f"Error in clarification_node: {e}")
        print(f"❌ Error in clarification_node: {e}")
        import traceback

        traceback.print_exc()
        raise
