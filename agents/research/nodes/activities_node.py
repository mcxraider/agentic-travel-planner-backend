"""
Activities node for the research graph.
"""

from typing import Any, Dict

from agents.research.nodes.base import run_research_node
from agents.research.prompts.builders import build_activities_prompts
from agents.research.prompts.templates import ActivitiesOutput


def activities_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate activity recommendations.

    Args:
        state: Current research state

    Returns:
        State updates for ``activities_output`` or repair routing fields.
    """
    return run_research_node(
        state,
        node_name="activities",
        output_key="activities_output",
        prompt_builder=build_activities_prompts,
        response_model=ActivitiesOutput,
    )
