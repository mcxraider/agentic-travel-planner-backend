"""
Graph construction for the research agent.

Builds and compiles the LangGraph workflow for destination research.
"""

from typing import Optional

from langgraph.graph import StateGraph, END

from agents.research.schemas import ResearchState
from agents.research.nodes.research import research_node
from agents.research.graph.config import ResearchGraphConfig, DEFAULT_CONFIG


def create_research_graph(
    config: Optional[ResearchGraphConfig] = None,
):
    """
    Create and compile the LangGraph workflow for research.

    The graph structure is:
        Entry -> research_node -> END

    Args:
        config: Optional configuration. Uses DEFAULT_CONFIG if not provided.

    Returns:
        Compiled LangGraph application ready for execution.
    """
    if config is None:
        config = DEFAULT_CONFIG

    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("research", research_node)

    # Set entry point and edges
    graph.set_entry_point("research")
    graph.add_edge("research", END)

    # Compile
    app = graph.compile()

    return app
