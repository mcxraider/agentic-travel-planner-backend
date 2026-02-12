"""
Graph configuration for the planner agent.

Centralizes configuration options for the planner LangGraph workflow.
"""

from dataclasses import dataclass


@dataclass
class PlannerGraphConfig:
    """
    Configuration for the planner graph.

    Attributes:
        recursion_limit: Maximum number of graph steps
        model: LLM model to use (for future LLM-powered planning)
        llm_timeout: LLM call timeout in seconds
        max_events_per_day: Maximum events to plan per day
    """

    recursion_limit: int = 10
    model: str = "gpt-4.1-mini"
    llm_timeout: int = 60
    max_events_per_day: int = 8


# Default configuration instance
DEFAULT_CONFIG = PlannerGraphConfig()
