"""
Top-level orchestrator graph.

Composes the research and planner agents into a sequential pipeline:
    clarification_output -> research -> planner -> done

The orchestrator takes completed ClarificationOutputV2 data as input
(clarification runs separately due to human-in-the-loop) and executes
research and planner agents sequentially.
"""

from agents.graph.build import create_orchestrator_graph

__all__ = ["create_orchestrator_graph"]
