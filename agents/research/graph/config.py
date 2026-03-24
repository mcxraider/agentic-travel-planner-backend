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
        recursion_limit: Maximum number of graph steps, including repair detours
        model: LLM model used by research nodes
        llm_timeout: LLM call timeout in seconds
        max_activities: Maximum activity recommendations to generate
        max_dining: Maximum dining recommendations to generate
        max_accommodation_areas: Maximum accommodation areas to generate
        max_highlights: Maximum highlights to generate
        max_repair_attempts: Maximum repair attempts for a parse/validation failure
        transient_max_attempts: Retry attempts for transient API failures
        transient_initial_interval: Initial retry backoff interval in seconds
        transient_backoff_factor: Exponential retry multiplier
        transient_max_interval: Maximum retry backoff interval in seconds
    """

    recursion_limit: int = 25
    model: str = "gpt-4.1"
    llm_timeout: int = 90
    max_repair_attempts: int = 2
    max_activities: int = 20
    max_dining: int = 15
    max_accommodation_areas: int = 5
    max_highlights: int = 8
    transient_max_attempts: int = 3
    transient_initial_interval: float = 1.0
    transient_backoff_factor: float = 2.0
    transient_max_interval: float = 10.0


# Default configuration instance
DEFAULT_CONFIG = ResearchGraphConfig()
