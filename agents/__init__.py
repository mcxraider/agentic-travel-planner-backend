"""
Agents package for the AI-powered trip planning application.

This package contains:
- shared/: Common infrastructure (LLM client, logging, contracts, schemas)
- clarification/: Clarification agent for gathering travel preferences
- research/: Research agent (future)
- planner/: Planner agent (future)
- validator/: Validator agent (future)
- orchestration/: Multi-agent orchestration (future)
"""

from agents.clarification.graph.build import create_clarification_graph

__all__ = ["create_clarification_graph"]
