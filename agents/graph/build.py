"""
Orchestrator graph construction.

Builds the top-level graph that sequences research -> planner agents.
Uses wrapper nodes to adapt orchestrator state into agent-specific graph inputs.
"""

import logging
from typing import Dict, Any

from langgraph.graph import StateGraph, END

from agents.graph.state import OrchestratorState
from agents.graph.router import route_next_agent
from agents.planner.nodes.planner import planner_node as _planner_node
from agents.research.graph.build import create_research_graph
from agents.research.schemas import ResearchState


logger = logging.getLogger(__name__)


def _research_wrapper(state: OrchestratorState) -> Dict[str, Any]:
    """
    Wrapper that adapts orchestrator state to the staged research graph.

    Extracts clarification preferences, initializes the research graph state,
    invokes the compiled research graph with a checkpoint thread id, and
    merges research output back into the orchestrator state.

    Args:
        state: Current orchestrator state

    Returns:
        State updates with research_output and tracking messages
    """
    session_id = state.get("session_id") or "unknown"
    _log = f"[session={session_id}] [graph=orchestrator] [node=research_wrapper] "

    logger.info(
        f"{_log}Entering node | destination={state['destination']}, "
        f"duration={state['trip_duration']}d, budget={state['budget']} {state['currency']}"
    )

    # Extract clarification preferences
    clarification = state.get("clarification_output") or {}
    has_prefs = (
        len([v for v in clarification.values() if v is not None])
        if clarification
        else 0
    )
    logger.info(f"{_log}Clarification preferences available: {has_prefs} fields")

    research_state: ResearchState = {
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
        "dietary_restrictions": clarification.get("dietary_severity"),
        "top_3_must_dos": clarification.get("top_3_must_dos"),
        "budget_priority": clarification.get("budget_priority"),
        "tourist_vs_local": clarification.get("tourist_vs_local"),
        "clarification_output": clarification,
        "weather_output": None,
        "destination_overview_output": None,
        "budget_analysis_output": None,
        "accommodation_output": None,
        "activities_output": None,
        "dining_output": None,
        "transportation_output": None,
        "curated_highlights_output": None,
        "repair_target": None,
        "repair_attempt_count": 0,
        "last_bad_response": None,
        "last_repaired_node": None,
        "research_output": None,
        "research_complete": False,
        "errors": [],
        "messages": [],
        "session_id": session_id,
    }

    try:
        research_graph = create_research_graph()
        invoke_config = {"configurable": {"thread_id": f"research-{session_id}"}}

        logger.info(f"{_log}Delegating to staged research graph")
        result = research_graph.invoke(research_state, config=invoke_config)

        if not result.get("research_complete"):
            logger.error(
                "%s Research pipeline incomplete | errors=%s",
                _log,
                result.get("errors", []),
            )
        else:
            logger.info(f"{_log}Research graph returned successfully")

        return {
            "research_output": result.get("research_output"),
            "errors": result.get("errors", []),
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
