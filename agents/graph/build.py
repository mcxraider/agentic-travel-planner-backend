"""
Orchestrator graph construction.

Builds the top-level graph that sequences research -> planner agents.
Uses wrapper nodes that call agent node functions directly (not compiled
sub-graphs) to avoid state schema mismatches with single-node stubs.
"""

import logging
from typing import Dict, Any

from langgraph.graph import StateGraph, END

from agents.graph.state import OrchestratorState
from agents.graph.router import route_next_agent
from agents.research.nodes.research import research_node as _research_node
from agents.planner.nodes.planner import planner_node as _planner_node


logger = logging.getLogger(__name__)


def _research_wrapper(state: OrchestratorState) -> Dict[str, Any]:
    """
    Wrapper that adapts orchestrator state to research node interface.

    Extracts relevant fields from OrchestratorState, calls the research
    node function directly, and merges results back into orchestrator state.

    Args:
        state: Current orchestrator state

    Returns:
        State updates with research_output and tracking messages
    """
    session_id = state.get("session_id", "unknown")
    _log = f"[session={session_id}] [graph=orchestrator] [node=research_wrapper] "

    logger.info(
        f"{_log}Entering node | destination={state['destination']}, "
        f"duration={state['trip_duration']}d, budget={state['budget']} {state['currency']}"
    )

    # Extract clarification preferences
    clarification = state.get("clarification_output") or {}
    has_prefs = len([v for v in clarification.values() if v is not None]) if clarification else 0
    logger.info(f"{_log}Clarification preferences available: {has_prefs} fields")

    # Build research-compatible state dict
    research_state = {
        "destination": state["destination"],
        "destination_cities": state.get("destination_cities"),
        "start_date": state["start_date"],
        "end_date": state["end_date"],
        "trip_duration": state["trip_duration"],
        "budget": state["budget"],
        "currency": state["currency"],
        "travel_party": state["travel_party"],
        "activity_preferences": clarification.get("activity_preferences"),
        "pace_preference": clarification.get("pace_preference"),
        "dining_style": clarification.get("dining_style"),
        "accommodation_style": clarification.get("accommodation_style"),
        "mobility_level": clarification.get("mobility_level"),
        "research_output": None,
        "research_complete": False,
        "messages": [],
        "session_id": state.get("session_id"),
    }

    try:
        logger.info(f"{_log}Delegating to research_node")
        result = _research_node(research_state)
        logger.info(f"{_log}Research node returned successfully")
        return {
            "research_output": result.get("research_output"),
            "current_agent": "research_complete",
            "messages": result.get("messages", []),
        }
    except Exception as e:
        logger.exception(f"{_log}Research agent failed: {e}")
        return {
            "current_agent": "research_failed",
            "errors": [f"Research agent error: {str(e)}"],
            "messages": [
                {
                    "role": "system",
                    "agent": "orchestrator",
                    "content": f"Research agent failed: {str(e)}",
                }
            ],
        }


def _planner_wrapper(state: OrchestratorState) -> Dict[str, Any]:
    """
    Wrapper that adapts orchestrator state to planner node interface.

    Extracts relevant fields from OrchestratorState, calls the planner
    node function directly, and merges results back into orchestrator state.

    Args:
        state: Current orchestrator state

    Returns:
        State updates with planner_output and tracking messages
    """
    session_id = state.get("session_id", "unknown")
    _log = f"[session={session_id}] [graph=orchestrator] [node=planner_wrapper] "

    has_research = state.get("research_output") is not None
    logger.info(
        f"{_log}Entering node | research_available={has_research}, "
        f"destination={state['destination']}"
    )

    # Extract clarification preferences
    clarification = state.get("clarification_output") or {}

    # Build planner-compatible state dict
    planner_state = {
        "destination": state["destination"],
        "destination_cities": state.get("destination_cities"),
        "start_date": state["start_date"],
        "end_date": state["end_date"],
        "trip_duration": state["trip_duration"],
        "budget": state["budget"],
        "currency": state["currency"],
        "travel_party": state["travel_party"],
        "activity_preferences": clarification.get("activity_preferences"),
        "pace_preference": clarification.get("pace_preference"),
        "dining_style": clarification.get("dining_style"),
        "daily_rhythm": clarification.get("daily_rhythm"),
        "arrival_time": clarification.get("arrival_time"),
        "departure_time": clarification.get("departure_time"),
        "research_output": state.get("research_output"),
        "planner_output": None,
        "planner_complete": False,
        "messages": [],
        "session_id": state.get("session_id"),
    }

    try:
        logger.info(f"{_log}Delegating to planner_node")
        result = _planner_node(planner_state)
        logger.info(f"{_log}Planner node returned successfully")
        return {
            "planner_output": result.get("planner_output"),
            "current_agent": "planner_complete",
            "messages": result.get("messages", []),
        }
    except Exception as e:
        logger.exception(f"{_log}Planner agent failed: {e}")
        return {
            "current_agent": "planner_failed",
            "errors": [f"Planner agent error: {str(e)}"],
            "messages": [
                {
                    "role": "system",
                    "agent": "orchestrator",
                    "content": f"Planner agent failed: {str(e)}",
                }
            ],
        }


def _complete_node(state: OrchestratorState) -> Dict[str, Any]:
    """
    Final node that marks the orchestrator pipeline as complete.

    Args:
        state: Current orchestrator state

    Returns:
        Completion tracking message
    """
    session_id = state.get("session_id", "unknown")
    _log = f"[session={session_id}] [graph=orchestrator] [node=complete] "

    has_research = state.get("research_output") is not None
    has_planner = state.get("planner_output") is not None
    num_errors = len(state.get("errors", []))

    logger.info(
        f"{_log}Pipeline complete | "
        f"research={'done' if has_research else 'MISSING'}, "
        f"planner={'done' if has_planner else 'MISSING'}, "
        f"errors={num_errors} -> END"
    )

    return {
        "current_agent": "complete",
        "messages": [
            {
                "role": "system",
                "agent": "orchestrator",
                "content": (
                    f"Pipeline complete. "
                    f"Research: {'done' if has_research else 'missing'}. "
                    f"Planner: {'done' if has_planner else 'missing'}."
                ),
            }
        ],
    }


def create_orchestrator_graph():
    """
    Create and compile the orchestrator graph.

    The graph structure is:
        Entry -> route_next_agent
          -> "research_node" -> research_wrapper -> route_next_agent
          -> "planner_node"  -> planner_wrapper  -> route_next_agent
          -> "complete"      -> complete_node     -> END

    Returns:
        Compiled LangGraph application ready for execution.
    """
    graph = StateGraph(OrchestratorState)

    # Add nodes
    graph.add_node("research_node", _research_wrapper)
    graph.add_node("planner_node", _planner_wrapper)
    graph.add_node("complete", _complete_node)

    # Conditional entry point - start from wherever state requires
    graph.set_conditional_entry_point(
        route_next_agent,
        {
            "research_node": "research_node",
            "planner_node": "planner_node",
            "complete": "complete",
        },
    )

    # After research, route again (goes to planner or complete)
    graph.add_conditional_edges(
        "research_node",
        route_next_agent,
        {
            "research_node": "research_node",
            "planner_node": "planner_node",
            "complete": "complete",
        },
    )

    # After planner, route again (goes to complete)
    graph.add_conditional_edges(
        "planner_node",
        route_next_agent,
        {
            "research_node": "research_node",
            "planner_node": "planner_node",
            "complete": "complete",
        },
    )

    # Complete -> END
    graph.add_edge("complete", END)

    app = graph.compile()

    return app
