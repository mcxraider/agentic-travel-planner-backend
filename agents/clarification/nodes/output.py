"""
Output node for the clarification LangGraph workflow.

Final node that formats and logs the completed clarification data.
"""

import json
import logging
from typing import Dict, Any

from agents.clarification.schemas import ClarificationState
from agents.shared.contracts.clarification_output import ClarificationOutput


logger = logging.getLogger("agents.clarification")


def output_node(state: ClarificationState) -> Dict[str, Any]:
    """
    Final output generator - formats and logs the collected data.

    This node is executed when clarification is complete. It:
    1. Logs a summary of the completed clarification
    2. Validates the output against the contract schema
    3. Returns the final state (unchanged)

    Args:
        state: Current clarification state with completed data

    Returns:
        Empty dict (no state changes needed at this point)
    """
    # Log completion summary
    print("\n" + "=" * 80)
    print("CLARIFICATION COMPLETE!")
    print("=" * 80)
    print(f"\nCompleteness Score: {state['completeness_score']}/100")
    print(f"Rounds Completed: {state['current_round']}")
    print("\nCollected Data:")
    print(json.dumps(state["collected_data"], indent=2))
    print("=" * 80 + "\n")

    # Log structured event
    logger.info(
        "Clarification complete",
        extra={
            "event": "clarification_complete",
            "completeness_score": state["completeness_score"],
            "rounds_completed": state["current_round"],
            "collected_fields": list(state["collected_data"].keys()),
        },
    )

    # Validate against output contract (optional - for downstream agents)
    try:
        collected = state["collected_data"]
        output = ClarificationOutput(
            activity_preferences=collected.get("activity_preferences", []),
            primary_activity_focus=collected.get("primary_activity_focus"),
            destination_specific_interests=collected.get(
                "destination_specific_interests", []
            ),
            pace_preference=collected.get("pace_preference"),
            tourist_vs_local_preference=collected.get("tourist_vs_local_preference"),
            schedule_preference=collected.get("schedule_preference"),
            mobility_walking_capacity=collected.get("mobility_walking_capacity"),
            dining_style=collected.get("dining_style", []),
            transportation_preference=collected.get("transportation_preference", []),
            arrival_time=collected.get("arrival_time"),
            departure_time=collected.get("departure_time"),
            special_logistics=collected.get("special_logistics"),
            wifi_need=collected.get("wifi_need"),
            completeness_score=state["completeness_score"],
            rounds_completed=state["current_round"],
        )
        logger.info(
            "Output contract validation successful",
            extra={"validated_output": output.model_dump()},
        )
    except Exception as e:
        logger.warning(
            f"Output contract validation failed: {e}",
            extra={"collected_data": state["collected_data"]},
        )

    # Return empty dict - no state changes needed
    # The state is already complete from the clarification node
    return {}
