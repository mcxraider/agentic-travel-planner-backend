"""
Dining node for the research graph.
"""

from typing import Any, Dict

from agents.research.nodes.base import run_research_node
from agents.research.prompts.builders import build_dining_prompts
from agents.research.prompts.templates import DiningOutput


def dining_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate dining recommendations.

    Args:
        state: Current research state

    Returns:
        State updates for ``dining_output`` or repair routing fields.
    """
    return run_research_node(
        state,
        node_name="dining",
        output_key="dining_output",
        prompt_builder=build_dining_prompts,
        response_model=DiningOutput,
    )
