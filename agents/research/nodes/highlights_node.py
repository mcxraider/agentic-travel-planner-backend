"""
Highlights node for the research graph.
"""

from typing import Any, Dict

from agents.research.nodes.base import run_research_node
from agents.research.prompts.builders import build_highlights_prompts
from agents.research.prompts.templates import HighlightsOutput


def highlights_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate curated highlights synthesized from prior research outputs.

    Args:
        state: Current research state

    Returns:
        State updates for ``curated_highlights_output`` or repair routing fields.
    """
    return run_research_node(
        state,
        node_name="highlights",
        output_key="curated_highlights_output",
        prompt_builder=build_highlights_prompts,
        response_model=HighlightsOutput,
    )
