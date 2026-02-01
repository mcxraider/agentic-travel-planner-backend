"""
Graph configuration for the clarification agent.

Centralizes all configuration options for the LangGraph workflow,
making it easy to tune behavior without modifying the graph wiring.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class GraphConfig:
    """
    Configuration for the clarification graph.

    Attributes:
        recursion_limit: Maximum number of graph steps (prevents infinite loops)
        interrupt_after: List of node names to pause after (for human-in-the-loop)
        max_rounds: Maximum clarification rounds before forcing completion
        min_completeness_score: Minimum score to consider clarification complete
        enable_checkpointing: Whether to enable state checkpointing
    """

    # Graph execution limits
    recursion_limit: int = 30

    # Human-in-the-loop configuration
    # Pause after clarification to wait for user input
    interrupt_after: List[str] = field(default_factory=lambda: ["clarification"])

    # Clarification rules
    max_rounds: int = 3
    min_completeness_score: int = 80

    # Persistence
    enable_checkpointing: bool = True

    # LLM configuration
    model: str = "gpt-4.1-mini"
    llm_timeout: int = 60  # seconds

    # Retry configuration (used by tenacity in llm/client.py)
    max_retries: int = 3
    retry_min_wait: int = 2  # seconds
    retry_max_wait: int = 10  # seconds


# Default configuration instance
DEFAULT_CONFIG = GraphConfig()
