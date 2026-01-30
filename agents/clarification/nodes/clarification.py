"""
Clarification node for the LangGraph workflow.

This is the main node that calls the LLM to generate questions
or complete the clarification process.
"""

import logging
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
from agents.shared.llm.client import get_cached_client, get_llm_response


logger = logging.getLogger("agents.clarification")


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

        # Call LLM
        llm_response = get_llm_response(client, user_prompt, system_prompt)

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
