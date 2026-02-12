"""
Research Agent for gathering destination data.

This agent researches destinations, POIs, logistics, and budget
information to feed into the planner agent. Currently uses mock
data; will be replaced with LLM-powered research.
"""

from agents.research.schemas import ResearchState
from agents.research.graph.build import create_research_graph

__all__ = ["ResearchState", "create_research_graph"]
