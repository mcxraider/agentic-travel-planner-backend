"""
Weather node for the research graph.
"""

from typing import Any, Dict

from agents.research.nodes.base import run_research_node
from agents.research.prompts.builders import build_weather_prompts
from agents.research.prompts.templates import WeatherInfo


def weather_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate destination weather guidance.

    Args:
        state: Current research state

    Returns:
        State updates for ``weather_output`` or repair routing fields.
    """
    return run_research_node(
        state,
        node_name="weather",
        output_key="weather_output",
        prompt_builder=build_weather_prompts,
        response_model=WeatherInfo,
    )
