"""
Graph construction for the research agent.

Builds and compiles the staged LangGraph workflow for destination research.
"""

from typing import Optional

import openai
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from agents.research.graph.config import DEFAULT_CONFIG, ResearchGraphConfig
from agents.research.graph.routing import (
    route_after_accommodation,
    route_after_activities,
    route_after_budget,
    route_after_dining,
    route_after_highlights,
    route_after_overview,
    route_after_repair,
    route_after_transport,
    route_after_weather,
)
from agents.research.nodes.accommodation_node import accommodation_node
from agents.research.nodes.activities_node import activities_node
from agents.research.nodes.aggregate_node import aggregate_node, degraded_aggregate_node
from agents.research.nodes.budget_node import budget_node
from agents.research.nodes.dining_node import dining_node
from agents.research.nodes.highlights_node import highlights_node
from agents.research.nodes.overview_node import overview_node
from agents.research.nodes.repair_node import repair_node
from agents.research.nodes.transport_node import transport_node
from agents.research.nodes.weather_node import weather_node
from agents.research.schemas import ResearchState
from agents.shared.logging import configure_terminal_logging


_TRANSIENT_ERRORS = (
    openai.APIError,
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
)


def _build_retry_policy(config: ResearchGraphConfig) -> RetryPolicy:
    """
    Build the retry policy applied to transient LLM/API failures.

    Args:
        config: Research graph runtime configuration

    Returns:
        LangGraph retry policy for transient upstream errors
    """
    return RetryPolicy(
        max_attempts=config.transient_max_attempts,
        initial_interval=config.transient_initial_interval,
        backoff_factor=config.transient_backoff_factor,
        max_interval=config.transient_max_interval,
        retry_on=_TRANSIENT_ERRORS,
    )


def create_research_graph(
    config: Optional[ResearchGraphConfig] = None,
    checkpointer=None,
) -> CompiledStateGraph:
    """
    Create and compile the staged LangGraph workflow for research.

    Args:
        config: Optional configuration. Uses DEFAULT_CONFIG if not provided.
        checkpointer: Optional LangGraph checkpointer. Defaults to MemorySaver.

    Returns:
        Compiled LangGraph application ready for execution.
    """
    configure_terminal_logging()

    if config is None:
        config = DEFAULT_CONFIG
    if checkpointer is None:
        checkpointer = MemorySaver()

    retry_policy = _build_retry_policy(config)
    graph = StateGraph(ResearchState)

    for name, fn in [
        ("weather", weather_node),
        ("overview", overview_node),
        ("budget", budget_node),
        ("accommodation", accommodation_node),
        ("activities", activities_node),
        ("dining", dining_node),
        ("transport", transport_node),
        ("highlights", highlights_node),
    ]:
        graph.add_node(name, fn, retry_policy=retry_policy)

    graph.add_node("repair", repair_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("degraded_aggregate", degraded_aggregate_node)

    graph.set_entry_point("weather")

    graph.add_conditional_edges(
        "weather",
        route_after_weather,
        {"overview": "overview", "repair": "repair"},
    )
    graph.add_conditional_edges(
        "overview",
        route_after_overview,
        {"budget": "budget", "repair": "repair"},
    )
    graph.add_conditional_edges(
        "budget",
        route_after_budget,
        {"accommodation": "accommodation", "repair": "repair"},
    )
    graph.add_conditional_edges(
        "accommodation",
        route_after_accommodation,
        {"activities": "activities", "repair": "repair"},
    )
    graph.add_conditional_edges(
        "activities",
        route_after_activities,
        {"dining": "dining", "repair": "repair"},
    )
    graph.add_conditional_edges(
        "dining",
        route_after_dining,
        {"transport": "transport", "repair": "repair"},
    )
    graph.add_conditional_edges(
        "transport",
        route_after_transport,
        {"highlights": "highlights", "repair": "repair"},
    )
    graph.add_conditional_edges(
        "highlights",
        route_after_highlights,
        {"aggregate": "aggregate", "repair": "repair"},
    )
    graph.add_conditional_edges(
        "repair",
        route_after_repair,
        {
            "overview": "overview",
            "budget": "budget",
            "accommodation": "accommodation",
            "activities": "activities",
            "dining": "dining",
            "transport": "transport",
            "highlights": "highlights",
            "aggregate": "aggregate",
            "degraded_aggregate": "degraded_aggregate",
        },
    )

    graph.add_edge("aggregate", END)
    graph.add_edge("degraded_aggregate", END)

    return graph.compile(checkpointer=checkpointer)
