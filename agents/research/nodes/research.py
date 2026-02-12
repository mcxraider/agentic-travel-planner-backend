"""
Research node for the LangGraph workflow.

Main node that performs destination research. Currently uses mock data;
will be replaced with LLM-powered research in the future.
"""

import logging
from typing import Dict, Any

from agents.research.schemas import ResearchState
from agents.research.mock_data import generate_mock_research
from agents.shared.contracts.research_output import ResearchOutputV1


logger = logging.getLogger(__name__)


def research_node(state: ResearchState) -> Dict[str, Any]:
    """
    Main research node that gathers destination data.

    Currently generates mock data. In production, this will call
    LLMs and external APIs for real research.

    Args:
        state: Current research state with trip context

    Returns:
        Dictionary with state updates including research_output
    """
    session_id = state.get("session_id", "unknown")
    _log = f"[session={session_id}] [graph=orchestrator] [node=research] "

    cities = state.get("destination_cities") or []
    logger.info(
        f"{_log}Entering node | destination={state['destination']}, "
        f"cities={cities}, duration={state['trip_duration']}d, "
        f"budget={state['budget']} {state['currency']}"
    )

    # Generate mock research data
    research_output = generate_mock_research(
        destination=state["destination"],
        destination_cities=state.get("destination_cities"),
        trip_duration=state["trip_duration"],
        budget=state["budget"],
        currency=state["currency"],
        travel_party=state["travel_party"],
        activity_preferences=state.get("activity_preferences"),
        accommodation_style=state.get("accommodation_style"),
    )

    # Validate against contract
    validated = ResearchOutputV1.model_validate(research_output.model_dump())

    total_pois = sum(len(c.pois) for c in validated.cities)
    logger.info(
        f"{_log}Research complete | cities={len(validated.cities)}, "
        f"pois={total_pois}, budget_assessment={validated.budget_analysis.budget_assessment}"
    )

    return {
        "research_output": validated.model_dump(),
        "research_complete": True,
        "messages": [
            {
                "role": "system",
                "agent": "research",
                "content": (
                    f"Research complete for {state['destination']}. "
                    f"Researched {len(validated.cities)} cities with "
                    f"{sum(len(c.pois) for c in validated.cities)} POIs."
                ),
            }
        ],
    }
