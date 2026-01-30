"""
Graph construction for the clarification agent.

Builds and compiles the LangGraph workflow with nodes, edges, and configuration.
"""

from typing import Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.clarification.schemas import ClarificationState
from agents.clarification.nodes.clarification import clarification_node
from agents.clarification.nodes.routing import should_continue
from agents.clarification.nodes.output import output_node
from agents.clarification.graph.config import GraphConfig, DEFAULT_CONFIG


def create_clarification_graph(
    config: Optional[GraphConfig] = None,
):
    """
    Create and compile the LangGraph workflow for clarification.

    The graph structure is:
        Entry → clarification_node → should_continue()
                                        ├→ If complete → output_node → END
                                        └→ Else → Loop back to clarification

    Args:
        config: Optional configuration. Uses DEFAULT_CONFIG if not provided.

    Returns:
        Compiled LangGraph application ready for execution.
    """
    if config is None:
        config = DEFAULT_CONFIG

    # Create the state graph
    graph = StateGraph(ClarificationState)

    # Add nodes
    graph.add_node("clarification", clarification_node)
    graph.add_node("output", output_node)

    # Set entry point
    graph.set_entry_point("clarification")

    # Add conditional routing after clarification
    graph.add_conditional_edges(
        "clarification",
        should_continue,
        {
            "clarification": "clarification",  # Loop back for more questions
            "output": "output",  # Move to final output
        },
    )

    # End after output
    graph.add_edge("output", END)

    # Compile with optional checkpointing
    compile_kwargs = {}

    if config.enable_checkpointing:
        memory = MemorySaver()
        compile_kwargs["checkpointer"] = memory

    if config.interrupt_after:
        compile_kwargs["interrupt_after"] = config.interrupt_after

    app = graph.compile(**compile_kwargs)

    return app


def create_graph_without_interrupts(
    config: Optional[GraphConfig] = None,
):
    """
    Create a graph that runs to completion without interrupts.

    Useful for testing or batch processing where human-in-the-loop
    is not needed.

    Args:
        config: Optional base configuration to modify.

    Returns:
        Compiled LangGraph application without interrupts.
    """
    if config is None:
        config = GraphConfig(interrupt_after=[], enable_checkpointing=False)
    else:
        # Override interrupt settings
        config = GraphConfig(
            recursion_limit=config.recursion_limit,
            interrupt_after=[],
            max_rounds=config.max_rounds,
            min_completeness_score=config.min_completeness_score,
            enable_checkpointing=False,
            model=config.model,
        )

    return create_clarification_graph(config)
