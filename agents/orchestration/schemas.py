"""
Orchestration schemas (future placeholder).

This module will define state schemas for multi-agent coordination.
"""

from typing import TypedDict, Optional, List


class OrchestrationState(TypedDict):
    """State for multi-agent orchestration (placeholder)."""

    # Current agent being executed
    current_agent: Optional[str]

    # Completed agents
    completed_agents: List[str]

    # Failed agents
    failed_agents: List[str]

    # Overall status
    status: str
