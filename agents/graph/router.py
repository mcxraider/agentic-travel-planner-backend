"""
Routing logic for the orchestrator graph.

Determines which agent to run next based on what data has been populated.
"""

import logging
from typing import Literal

from agents.graph.state import OrchestratorState


logger = logging.getLogger(__name__)


def route_next_agent(
    state: OrchestratorState,
) -> Literal["research_node", "planner_node", "complete"]:
    """
    Determine the next agent to execute based on populated state.

    Routing logic:
    1. If research_output is missing -> run research
    2. If planner_output is missing -> run planner
    3. Otherwise -> complete

    Args:
        state: Current orchestrator state

    Returns:
        Name of the next node to execute
    """
    session_id = state.get("session_id", "unknown")
    has_research = state.get("research_output") is not None
    has_planner = state.get("planner_output") is not None
    _log = f"[session={session_id}] [graph=orchestrator] [router=route_next_agent] "

    if not has_research:
        logger.info(
            f"{_log}Routing to 'research_node' | "
            f"research={has_research}, planner={has_planner}"
        )
        return "research_node"

    if not has_planner:
        logger.info(
            f"{_log}Routing to 'planner_node' | "
            f"research={has_research}, planner={has_planner}"
        )
        return "planner_node"

    logger.info(
        f"{_log}Routing to 'complete' | "
        f"research={has_research}, planner={has_planner}"
    )
    return "complete"
