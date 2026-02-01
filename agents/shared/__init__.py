"""
Shared infrastructure for all agents.

Modules:
- llm: OpenAI client with retry logic
- logging: Debug logging
- contracts: Agent output contracts for handoffs
"""

from agents.shared.llm.client import get_cached_client

__all__ = [
    "get_cached_client",
]
