"""
Output node for the clarification LangGraph workflow.

Final node that formats and logs the completed clarification data.
"""

import json
import logging
from typing import Dict, Any

from agents.clarification.schemas import ClarificationState
from agents.shared.contracts.clarification_output import ClarificationOutput, ClarificationOutputV2


logger = logging.getLogger("agents.clarification")


def output_node(state: ClarificationState) -> Dict[str, Any]:
    """
    Final output generator - formats and logs the collected data.

    This node is executed when clarification is complete. It:
    1. Logs a summary of the completed clarification
    2. Validates the output against the v2 contract schema
    3. Returns the final state (unchanged)

    Args:
        state: Current clarification state with completed data

    Returns:
        Empty dict (no state changes needed at this point)
    """
    # V2: Use data object if available, fall back to collected_data
    data = state.get("data") or state.get("collected_data", {})

    # Log completion summary
    print("\n" + "=" * 80)
    print("CLARIFICATION COMPLETE (V2)!")
    print("=" * 80)
    print(f"\nCompleteness Score: {state['completeness_score']}/100")
    print(f"Rounds Completed: {state['current_round']}")
    print("\nCollected Data (V2):")
    print(json.dumps(data, indent=2))
    print("=" * 80 + "\n")

    # Log structured event
    collected_fields = [k for k, v in data.items() if v is not None and not k.startswith("_")]
    logger.info(
        "Clarification complete (v2)",
        extra={
            "event": "clarification_complete_v2",
            "completeness_score": state["completeness_score"],
            "rounds_completed": state["current_round"],
            "collected_fields": collected_fields,
        },
    )

    # Validate against v2 output contract (for downstream agents)
    try:
        output = ClarificationOutputV2.from_data(
            data=data,
            completeness_score=state["completeness_score"],
            rounds_completed=state["current_round"],
        )
        logger.info(
            "V2 output contract validation successful",
            extra={"validated_output": output.model_dump()},
        )
    except Exception as e:
        logger.warning(
            f"V2 output contract validation failed: {e}",
            extra={"data": data},
        )

    # Return empty dict - no state changes needed
    # The state is already complete from the clarification node
    return {}
