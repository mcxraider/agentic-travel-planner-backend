"""
Base agent state schema.

Defines the common state fields shared across all agent TypedDicts.
"""

from typing import TypedDict, List, Optional, Annotated
import operator


class BaseAgentState(TypedDict):
    """
    Base state schema with fields common to all agents.

    All agent-specific state schemas should include these fields.
    Since TypedDict doesn't support inheritance cleanly with LangGraph,
    agents should copy these fields into their own state schemas.

    Fields:
        session_id: Unique session identifier for tracking
        messages: Append-only list of tracking messages (uses operator.add)
    """

    session_id: Optional[str]
    messages: Annotated[List[dict], operator.add]
