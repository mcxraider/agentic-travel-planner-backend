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
    build_system_prompt,
    build_user_prompt,
)
from agents.clarification.response_parser import (
    parse_clarification_response,
    build_state_update_for_questions,
    build_state_update_for_completion,
    ParseError,
)
from agents.shared.llm.client import get_cached_client, get_llm_response_with_usage
from agents.shared.logging.debug_logger import get_or_create_logger


logger = logging.getLogger("agents.clarification")

# Default model for clarification
DEFAULT_MODEL = "gpt-5-mini"


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

        # Build prompts
        system_prompt = build_system_prompt(state)
        user_prompt = build_user_prompt(state)

        # Get debug logger from registry if session_id is available
        session_id = state.get("session_id")
        debug_logger = get_or_create_logger(session_id) if session_id else None

        # Log the call
        logger.info(
            f"Round {state['current_round']} - Calling LLM",
            extra={
                "round": state["current_round"],
                "collected_data_keys": list(state.get("collected_data", {}).keys()),
                "completeness_score": state.get("completeness_score", 0),
            },
        )

        # Debug output (for development)
        print("\n" + "=" * 80)
        print(f"🤖 Round {state['current_round']} - Calling LLM")
        print("=" * 80)
        print(f"\n📋 USER PROMPT:\n{user_prompt}")
        print(f"\n📊 State Debug:")
        print(f"   - collected_data: {state.get('collected_data', {})}")
        print(f"   - current_round: {state['current_round']}")
        print(f"   - completeness_score: {state.get('completeness_score', 0)}")
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
        print(f"\n📈 Token Usage: {usage['input_tokens']} in / {usage['output_tokens']} out")
        print(f"⏱️  LLM Duration: {duration_ms:.2f}ms")

        # Parse response
        is_complete, parsed_data = parse_clarification_response(llm_response)

        # Build state update based on response type
        if is_complete:
            result = build_state_update_for_completion(parsed_data)
        else:
            result = build_state_update_for_questions(state, parsed_data)

        # Log completion
        print(
            f"✅ Round {state['current_round']} completed - "
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
