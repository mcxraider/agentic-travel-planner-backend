"""
Routing logic for the clarification LangGraph workflow.

Determines the next node to execute based on current state.
"""

from typing import Literal

from agents.clarification.schemas import ClarificationState


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
    if state.get("clarification_complete", False):
        return "output"
    else:
        return "clarification"
