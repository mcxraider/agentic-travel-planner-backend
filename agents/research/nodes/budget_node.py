"""
Budget node for the research graph.
"""

from typing import Any, Dict

from agents.research.nodes.base import run_research_node
from agents.research.prompts.builders import build_budget_prompts
from agents.research.prompts.templates import InDestinationBudget


def budget_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate in-destination budget analysis.

    Args:
        state: Current research state

    Returns:
        State updates for ``budget_analysis_output`` or repair routing fields.
    """
    return run_research_node(
        state,
        node_name="budget",
        output_key="budget_analysis_output",
        prompt_builder=build_budget_prompts,
        response_model=InDestinationBudget,
    )
