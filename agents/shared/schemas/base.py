"""
Common base schemas used across agents.

Provides base models and types that are shared between multiple agents.
"""

from typing import TypedDict, List, Optional, Annotated
import operator


class BaseAgentState(TypedDict):
    """
    Base state schema for all agents.

    All agent states should inherit from this to ensure consistent
    message handling across the system.
    """

    # Messages for tracking conversation history
    # Uses operator.add for automatic message accumulation
    messages: Annotated[List[dict], operator.add]
