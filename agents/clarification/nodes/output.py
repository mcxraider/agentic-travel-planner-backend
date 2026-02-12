"""
Output node for the clarification LangGraph workflow.

Final node that formats and logs the completed clarification data.
"""

import json
import logging
from typing import Dict, Any

from agents.clarification.schemas import ClarificationState
from agents.shared.contracts.clarification_output import ClarificationOutputV2


logger = logging.getLogger(__name__)


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
    session_id = state.get("session_id", "unknown")
    _log = f"[session={session_id}] [graph=clarification] [node=output] "

    # V2: Use data object if available, fall back to collected_data
    data = state.get("data") or state.get("collected_data", {})

    collected_fields = [
        k for k, v in data.items() if v is not None and not k.startswith("_")
    ]
    missing_fields = [
        k for k, v in data.items() if v is None and not k.startswith("_")
    ]

    logger.info(
        f"{_log}Entering node | score={state['completeness_score']}/100, "
        f"rounds={state['current_round']}, "
        f"fields_collected={len(collected_fields)}/{len(collected_fields) + len(missing_fields)}"
    )
    logger.info(f"{_log}Collected: {collected_fields}")
    logger.debug(f"{_log}Missing: {missing_fields}")
    logger.debug(
        f"{_log}Full data: {json.dumps(data, ensure_ascii=True, sort_keys=True)}"
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
