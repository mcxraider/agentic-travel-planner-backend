"""
Schemas for the planner agent.

Defines the state schema for LangGraph and any planner-specific models.
"""

from typing import TypedDict, List, Optional, Annotated
import operator


class PlannerState(TypedDict):
    """
    State schema for the planner agent.

    This TypedDict defines all the data that flows through the LangGraph
    workflow during the planning process.
    """

    # Trip context
    destination: str
    destination_cities: Optional[List[str]]
    start_date: str
    end_date: str
    trip_duration: int
    budget: float
    currency: str
    travel_party: str

    # Clarification preferences (subset relevant to planning)
    activity_preferences: Optional[List[str]]
    pace_preference: Optional[str]
    dining_style: Optional[List[str]]
    daily_rhythm: Optional[str]
    arrival_time: Optional[str]
    departure_time: Optional[str]

    # Research data (input from research agent)
    research_output: Optional[dict]

    # Planner output (populated by planner_node)
    planner_output: Optional[dict]

    # Process tracking
    planner_complete: bool
    messages: Annotated[List[dict], operator.add]
    session_id: Optional[str]
