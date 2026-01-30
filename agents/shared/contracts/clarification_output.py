"""
Clarification agent output contract.

Defines the structured output that the clarification agent produces
for consumption by downstream agents (research, planner).
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ClarificationOutput(BaseModel):
    """
    Contract for clarification agent output.

    This model defines the exact structure of data that flows from
    the clarification agent to downstream agents (research, planner).
    """

    # Activity and interest preferences
    activity_preferences: List[str] = Field(
        default_factory=list,
        description="Selected activity types (e.g., 'nature / hiking', 'food / gastronomy')",
    )
    primary_activity_focus: Optional[str] = Field(
        default=None,
        description="Single primary focus derived from activity preferences",
    )
    destination_specific_interests: List[str] = Field(
        default_factory=list,
        description="Top activities/interests specific to the destination",
    )

    # Pace and style preferences
    pace_preference: Optional[str] = Field(
        default=None,
        description="Trip pacing: 'relaxed', 'moderate', or 'intense'",
    )
    tourist_vs_local_preference: Optional[str] = Field(
        default=None,
        description="Preference for tourist landmarks vs local spots",
    )
    schedule_preference: Optional[str] = Field(
        default=None,
        description="Daily schedule packing preference",
    )

    # Physical considerations
    mobility_walking_capacity: Optional[str] = Field(
        default=None,
        description="Walking capacity: minimal, moderate, or high",
    )

    # Dining and food
    dining_style: List[str] = Field(
        default_factory=list,
        description="Preferred dining styles (street food, casual, fine dining, etc.)",
    )

    # Transportation
    transportation_preference: List[str] = Field(
        default_factory=list,
        description="Preferred transportation modes",
    )

    # Timing
    arrival_time: Optional[str] = Field(
        default=None,
        description="Expected arrival time on first day",
    )
    departure_time: Optional[str] = Field(
        default=None,
        description="Expected departure time on last day",
    )

    # Logistics
    special_logistics: Optional[str] = Field(
        default=None,
        description="Free text for complex logistics needs",
    )
    wifi_need: Optional[str] = Field(
        default=None,
        description="WiFi importance level",
    )

    # Metadata
    completeness_score: int = Field(
        default=0,
        ge=0,
        le=100,
        description="How complete the clarification data is (0-100)",
    )
    rounds_completed: int = Field(
        default=0,
        ge=0,
        description="Number of clarification rounds completed",
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "activity_preferences": ["nature / hiking", "food / gastronomy"],
                "primary_activity_focus": "nature / hiking",
                "destination_specific_interests": [
                    "Rocky Mountain National Park",
                    "Local craft breweries",
                ],
                "pace_preference": "moderate",
                "tourist_vs_local_preference": "balanced mix",
                "mobility_walking_capacity": "moderate walking (~10k steps/day)",
                "dining_style": ["casual dining", "street food"],
                "transportation_preference": ["rental car"],
                "arrival_time": "Mid-morning (9am-12pm)",
                "departure_time": "Evening (after 5pm)",
                "wifi_need": "Preferred but not critical",
                "schedule_preference": "mostly moderate pacing",
                "completeness_score": 85,
                "rounds_completed": 2,
            }
        }
