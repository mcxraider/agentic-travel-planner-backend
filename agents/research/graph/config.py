"""
Graph configuration for the research agent.

Centralizes configuration options for the research LangGraph workflow.
"""

from dataclasses import dataclass


@dataclass
class ResearchGraphConfig:
    """
    Configuration for the research graph.

    Attributes:
        recursion_limit: Maximum number of graph steps
        model: LLM model to use (for future LLM-powered research)
        llm_timeout: LLM call timeout in seconds
        max_pois_per_city: Maximum POIs to research per city
    """

    recursion_limit: int = 10
    model: str = "gpt-4.1-mini"
    llm_timeout: int = 60
    max_pois_per_city: int = 15


# Default configuration instance
DEFAULT_CONFIG = ResearchGraphConfig()
