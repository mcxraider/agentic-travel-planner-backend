"""
Shared infrastructure for all agents.

Modules:
- llm: OpenAI client with retry logic
- logging: Structured JSON logging
- contracts: Agent output contracts for handoffs
- schemas: Common base models
"""

from agents.shared.llm.client import get_cached_client, call_llm
from agents.shared.logging.config import setup_logging, log_state_transition

__all__ = [
    "get_cached_client",
    "call_llm",
    "setup_logging",
    "log_state_transition",
]
