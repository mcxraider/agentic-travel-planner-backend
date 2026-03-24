"""
Schemas for the research agent.

Defines the LangGraph state used by the staged research pipeline.
"""

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class ResearchState(TypedDict):
    """
    State schema for the research agent workflow.

    This state carries trip context, clarification preferences, intermediate
    sub-agent outputs, repair-loop tracking, and the final validated result.
    """

    # Inputs from clarification/orchestrator
    destination: str
    destination_cities: Optional[List[str]]
    start_date: str
    end_date: str
    trip_duration: int
    budget: float
    currency: str
    travel_party: str
    activity_preferences: Optional[List[str]]
    pace_preference: Optional[str]
    dining_style: Optional[List[str]]
    accommodation_style: Optional[List[str]]
    mobility_level: Optional[str]
    dietary_restrictions: Optional[str]
    top_3_must_dos: Optional[Dict[str, str]]
    budget_priority: Optional[str]
    tourist_vs_local: Optional[str]
    clarification_output: Optional[Dict[str, Any]]

    # Per-node outputs
    weather_output: Optional[Dict[str, Any]]
    destination_overview_output: Optional[Dict[str, Any]]
    budget_analysis_output: Optional[Dict[str, Any]]
    accommodation_output: Optional[Dict[str, Any]]
    activities_output: Optional[Dict[str, Any]]
    dining_output: Optional[Dict[str, Any]]
    transportation_output: Optional[Dict[str, Any]]
    curated_highlights_output: Optional[Dict[str, Any]]

    # Final validated output
    research_output: Optional[Dict[str, Any]]
    research_complete: bool

    # Repair-loop state
    repair_target: Optional[str]
    repair_attempt_count: int
    last_bad_response: Optional[str]
    last_repaired_node: Optional[str]

    # Tracking
    errors: Annotated[List[str], operator.add]
    messages: Annotated[List[Dict[str, Any]], operator.add]
    session_id: Optional[str]
