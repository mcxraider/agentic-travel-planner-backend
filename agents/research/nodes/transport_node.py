"""
Transport node for the research graph.
"""

from typing import Any, Dict

from agents.research.nodes.base import run_research_node
from agents.research.prompts.builders import build_transport_prompts
from agents.research.prompts.templates import TransportOutput


def transport_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate local transportation recommendations.

    Args:
        state: Current research state

    Returns:
        State updates for ``transportation_output`` or repair routing fields.
    """
    return run_research_node(
        state,
        node_name="transport",
        output_key="transportation_output",
        prompt_builder=build_transport_prompts,
        response_model=TransportOutput,
    )
