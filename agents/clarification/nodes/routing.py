"""
Routing logic for the clarification LangGraph workflow.

Determines the next node to execute based on current state.
"""

import logging
from typing import Literal

from agents.clarification.schemas import ClarificationState


logger = logging.getLogger(__name__)


def should_continue(state: ClarificationState) -> Literal["output", "clarification"]:
    """
    Determine whether to continue asking questions or finish.

    This is the conditional routing function used by LangGraph to decide
    which edge to follow after the clarification node.

    Args:
        state: Current clarification state

    Returns:
        "output" if clarification is complete, "clarification" otherwise
    """
    session_id = state.get("session_id", "unknown")
    _log = f"[session={session_id}] [graph=clarification] [router=should_continue] "

    is_complete = state.get("clarification_complete", False)
    score = state.get("completeness_score", 0)
    current_round = state.get("current_round", 0)

    if is_complete:
        logger.info(
            f"{_log}Routing to 'output' | "
            f"round={current_round}, score={score}/100, complete=True"
        )
        return "output"
    else:
        logger.info(
            f"{_log}Routing to 'clarification' (loop) | "
            f"round={current_round}, score={score}/100, complete=False "
            f"-> will pause for human feedback"
        )
        return "clarification"
