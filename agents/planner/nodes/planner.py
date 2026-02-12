"""
Planner node for the LangGraph workflow.

Main node that generates a day-by-day itinerary. Currently uses mock data;
will be replaced with LLM-powered planning in the future.
"""

import logging
from typing import Dict, Any

from agents.planner.schemas import PlannerState
from agents.planner.mock_data import generate_mock_itinerary
from agents.shared.contracts.planner_output import PlannerOutputV1


logger = logging.getLogger(__name__)


def planner_node(state: PlannerState) -> Dict[str, Any]:
    """
    Main planner node that generates a day-by-day itinerary.

    Currently generates mock data. In production, this will use
    LLMs to create optimized itineraries from research data.

    Args:
        state: Current planner state with trip context and research data

    Returns:
        Dictionary with state updates including planner_output
    """
    session_id = state.get("session_id", "unknown")
    _log = f"[session={session_id}] [graph=orchestrator] [node=planner] "

    has_research = state.get("research_output") is not None
    logger.info(
        f"{_log}Entering node | destination={state['destination']}, "
        f"duration={state['trip_duration']}d, research_available={has_research}, "
        f"pace={state.get('pace_preference', 'N/A')}, rhythm={state.get('daily_rhythm', 'N/A')}"
    )

    # Generate mock itinerary
    planner_output = generate_mock_itinerary(
        destination=state["destination"],
        destination_cities=state.get("destination_cities"),
        start_date=state["start_date"],
        end_date=state["end_date"],
        trip_duration=state["trip_duration"],
        budget=state["budget"],
        currency=state["currency"],
        travel_party=state["travel_party"],
        research_output=state.get("research_output"),
        activity_preferences=state.get("activity_preferences"),
        pace_preference=state.get("pace_preference"),
        daily_rhythm=state.get("daily_rhythm"),
        arrival_time=state.get("arrival_time"),
        departure_time=state.get("departure_time"),
    )

    # Validate against contract
    validated = PlannerOutputV1.model_validate(planner_output.model_dump())

    total_events = sum(len(d.events) for d in validated.days)
    logger.info(
        f"{_log}Planning complete | days={len(validated.days)}, "
        f"events={total_events}, "
        f"cost=${validated.cost_summary.total_estimated_usd:.2f}/{state['budget']}"
    )

    return {
        "planner_output": validated.model_dump(),
        "planner_complete": True,
        "messages": [
            {
                "role": "system",
                "agent": "planner",
                "content": (
                    f"Itinerary planned: '{validated.trip_title}'. "
                    f"{len(validated.days)} days with "
                    f"{sum(len(d.events) for d in validated.days)} events. "
                    f"Estimated cost: ${validated.cost_summary.total_estimated_usd:.2f}"
                ),
            }
        ],
    }
