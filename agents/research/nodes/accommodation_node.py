"""
Accommodation node for the research graph.
"""

from typing import Any, Dict

from agents.research.nodes.base import run_research_node
from agents.research.prompts.builders import build_accommodation_prompts
from agents.research.prompts.templates import AccommodationAreasOutput


def accommodation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate accommodation area recommendations.

    Args:
        state: Current research state

    Returns:
        State updates for ``accommodation_output`` or repair routing fields.
    """
    return run_research_node(
        state,
        node_name="accommodation",
        output_key="accommodation_output",
        prompt_builder=build_accommodation_prompts,
        response_model=AccommodationAreasOutput,
    )
