"""
Planner agent output contract.

Defines the structured output that the planner agent produces
as the final day-by-day itinerary.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class ItineraryEvent(BaseModel):
    """A single event/activity within a day."""

    event_id: str = Field(description="Unique event identifier")
    time_slot: str = Field(
        description="Time slot (e.g., '09:00-11:00', 'Morning')"
    )
    title: str = Field(description="Event title")
    description: str = Field(description="Event description")
    category: str = Field(
        description="Category (e.g., 'dining', 'activity', 'transport', 'leisure')"
    )
    location: Optional[str] = Field(default=None, description="Event location/venue")
    estimated_cost_usd: Optional[float] = Field(
        default=None, description="Estimated cost in USD"
    )
    duration_hours: float = Field(
        ge=0.25, description="Duration in hours"
    )
    notes: Optional[str] = Field(
        default=None, description="Additional notes or tips"
    )


class ItineraryDay(BaseModel):
    """A single day in the itinerary."""

    day_number: int = Field(ge=1, description="Day number (1-indexed)")
    date: Optional[str] = Field(
        default=None, description="Date in YYYY-MM-DD format"
    )
    city: str = Field(description="City for this day")
    theme: str = Field(
        description="Day theme (e.g., 'Cultural Exploration', 'Beach & Relaxation')"
    )
    events: List[ItineraryEvent] = Field(
        default_factory=list, description="Scheduled events for this day"
    )
    day_cost_estimate_usd: Optional[float] = Field(
        default=None, description="Estimated total cost for this day"
    )


class CostSummary(BaseModel):
    """Overall trip cost summary."""

    total_estimated_usd: float = Field(description="Total estimated cost in USD")
    budget_usd: float = Field(description="Original budget in USD")
    remaining_usd: float = Field(description="Remaining budget after estimates")
    breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by category (e.g., {'accommodation': 200})",
    )


class PlannerOutputV1(BaseModel):
    """
    Contract for planner agent output (v1).

    This model defines the final day-by-day itinerary produced
    by the planner agent.
    """

    trip_title: str = Field(description="Generated trip title")
    destination: str = Field(description="Trip destination")
    start_date: str = Field(description="Trip start date (YYYY-MM-DD)")
    end_date: str = Field(description="Trip end date (YYYY-MM-DD)")
    trip_duration: int = Field(ge=1, description="Trip duration in days")
    days: List[ItineraryDay] = Field(
        default_factory=list, description="Day-by-day itinerary"
    )
    cost_summary: CostSummary = Field(description="Overall cost summary")
    planning_notes: List[str] = Field(
        default_factory=list,
        description="Planning notes, tips, and recommendations",
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional metadata (e.g., generated_at, version)",
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "trip_title": "Bali Adventure: Culture & Nature",
                "destination": "Bali, Indonesia",
                "start_date": "2025-03-01",
                "end_date": "2025-03-04",
                "trip_duration": 4,
                "days": [
                    {
                        "day_number": 1,
                        "date": "2025-03-01",
                        "city": "Ubud",
                        "theme": "Cultural Immersion",
                        "events": [
                            {
                                "event_id": "d1_e1",
                                "time_slot": "09:00-11:00",
                                "title": "Tegallalang Rice Terrace",
                                "description": "Explore the iconic rice paddies",
                                "category": "activity",
                                "location": "Tegallalang",
                                "estimated_cost_usd": 5.0,
                                "duration_hours": 2.0,
                            }
                        ],
                        "day_cost_estimate_usd": 85.0,
                    }
                ],
                "cost_summary": {
                    "total_estimated_usd": 340.0,
                    "budget_usd": 1500.0,
                    "remaining_usd": 1160.0,
                    "breakdown": {
                        "accommodation": 200.0,
                        "food": 80.0,
                        "transport": 40.0,
                        "activities": 20.0,
                    },
                },
                "planning_notes": [
                    "Book Mount Batur sunrise trek in advance"
                ],
            }
        }
