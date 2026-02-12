"""
Schemas for the research agent.

Defines the state schema for LangGraph and any research-specific models.
"""

from typing import TypedDict, List, Optional, Annotated
import operator


class ResearchState(TypedDict):
    """
    State schema for the research agent.

    This TypedDict defines all the data that flows through the LangGraph
    workflow during the research process.
    """

    # Trip context (passed in from orchestrator/clarification)
    destination: str
    destination_cities: Optional[List[str]]
    start_date: str
    end_date: str
    trip_duration: int
    budget: float
    currency: str
    travel_party: str

    # Clarification preferences (subset relevant to research)
    activity_preferences: Optional[List[str]]
    pace_preference: Optional[str]
    dining_style: Optional[List[str]]
    accommodation_style: Optional[List[str]]
    mobility_level: Optional[str]

    # Research output (populated by research_node)
    research_output: Optional[dict]

    # Process tracking
    research_complete: bool
    messages: Annotated[List[dict], operator.add]
    session_id: Optional[str]
