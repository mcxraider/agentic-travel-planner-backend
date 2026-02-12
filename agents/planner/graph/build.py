"""
Graph construction for the planner agent.

Builds and compiles the LangGraph workflow for itinerary planning.
"""

from typing import Optional

from langgraph.graph import StateGraph, END

from agents.planner.schemas import PlannerState
from agents.planner.nodes.planner import planner_node
from agents.planner.graph.config import PlannerGraphConfig, DEFAULT_CONFIG


def create_planner_graph(
    config: Optional[PlannerGraphConfig] = None,
):
    """
    Create and compile the LangGraph workflow for planning.

    The graph structure is:
        Entry -> planner_node -> END

    Args:
        config: Optional configuration. Uses DEFAULT_CONFIG if not provided.

    Returns:
        Compiled LangGraph application ready for execution.
    """
    if config is None:
        config = DEFAULT_CONFIG

    graph = StateGraph(PlannerState)

    # Add nodes
    graph.add_node("planner", planner_node)

    # Set entry point and edges
    graph.set_entry_point("planner")
    graph.add_edge("planner", END)

    # Compile
    app = graph.compile()

    return app
