"""
Graph configuration for the clarification agent.

Centralizes all configuration options for the LangGraph workflow,
making it easy to tune behavior without modifying the graph wiring.
"""

from dataclasses import dataclass, field
from typing import List, Optional


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


def get_config(
    recursion_limit: Optional[int] = None,
    interrupt_after: Optional[List[str]] = None,
    max_rounds: Optional[int] = None,
    min_completeness_score: Optional[int] = None,
    enable_checkpointing: Optional[bool] = None,
    model: Optional[str] = None,
) -> GraphConfig:
    """
    Create a configuration with optional overrides.

    Args:
        recursion_limit: Override for recursion limit
        interrupt_after: Override for interrupt nodes
        max_rounds: Override for max clarification rounds
        min_completeness_score: Override for min completeness score
        enable_checkpointing: Override for checkpointing flag
        model: Override for LLM model

    Returns:
        GraphConfig with specified overrides applied
    """
    return GraphConfig(
        recursion_limit=recursion_limit or DEFAULT_CONFIG.recursion_limit,
        interrupt_after=interrupt_after
        if interrupt_after is not None
        else DEFAULT_CONFIG.interrupt_after,
        max_rounds=max_rounds or DEFAULT_CONFIG.max_rounds,
        min_completeness_score=min_completeness_score
        or DEFAULT_CONFIG.min_completeness_score,
        enable_checkpointing=enable_checkpointing
        if enable_checkpointing is not None
        else DEFAULT_CONFIG.enable_checkpointing,
        model=model or DEFAULT_CONFIG.model,
    )
