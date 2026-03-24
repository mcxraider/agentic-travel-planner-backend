"""
Overview node for the research graph.
"""

from typing import Any, Dict

from agents.research.nodes.base import run_research_node
from agents.research.prompts.builders import build_overview_prompts
from agents.research.prompts.templates import DestinationOverviewOutput


def overview_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate destination overview content.

    Args:
        state: Current research state

    Returns:
        State updates for ``destination_overview_output`` or repair routing fields.
    """
    return run_research_node(
        state,
        node_name="overview",
        output_key="destination_overview_output",
        prompt_builder=build_overview_prompts,
        response_model=DestinationOverviewOutput,
    )
