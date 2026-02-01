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


class ClarificationOutputV2(BaseModel):
    """
    Contract for clarification agent output (v2).

    This model defines the exact structure of data that flows from
    the clarification agent to downstream agents (research, planner).
    Matches the v2 data schema with tiered fields.
    """

    # Tier 1: Critical
    activity_preferences: List[str] = Field(
        default_factory=list,
        description="Selected activity types (e.g., 'nature/hiking', 'food/gastronomy')",
    )
    pace_preference: Optional[str] = Field(
        default=None,
        description="Trip pacing: 'relaxed', 'moderate', or 'intense'",
    )
    tourist_vs_local: Optional[str] = Field(
        default=None,
        description="Preference: 'major landmarks', 'hidden gems', or 'balanced'",
    )
    mobility_level: Optional[str] = Field(
        default=None,
        description="Walking capacity: 'minimal', 'moderate', or 'high'",
    )
    dining_style: List[str] = Field(
        default_factory=list,
        description="Preferred dining styles",
    )

    # Tier 2: Planning Essentials
    top_3_must_dos: Optional[dict] = Field(
        default=None,
        description="Force-ranked top 3 activities: {'1': str, '2': str, '3': str}",
    )
    transportation_mode: List[str] = Field(
        default_factory=list,
        description="Preferred transportation modes",
    )
    arrival_time: Optional[str] = Field(
        default=None,
        description="Expected arrival time on first day",
    )
    departure_time: Optional[str] = Field(
        default=None,
        description="Expected departure time on last day",
    )
    budget_priority: Optional[str] = Field(
        default=None,
        description="Budget priority: 'experiences > comfort', 'balanced', 'comfort > experiences'",
    )
    accommodation_style: Optional[str] = Field(
        default=None,
        description="Accommodation style preference",
    )

    # Tier 3: Conditional Critical
    wifi_need: Optional[str] = Field(
        default=None,
        description="WiFi importance level (escalated if work_obligations exist)",
    )
    dietary_severity: Optional[str] = Field(
        default=None,
        description="Dietary restriction severity (escalated if dietary_restrictions exist)",
    )
    accessibility_needs: Optional[str] = Field(
        default=None,
        description="Accessibility requirements (escalated if health_limitations exist)",
    )

    # Tier 4: Optimization
    daily_rhythm: Optional[str] = Field(
        default=None,
        description="Daily rhythm: 'early bird', 'night owl', 'flexible'",
    )
    downtime_preference: Optional[str] = Field(
        default=None,
        description="Downtime preference: 'packed schedule', 'some rest', 'lots of flexibility'",
    )

    # Meta fields (renamed from underscore-prefixed)
    conflicts_resolved: List[str] = Field(
        default_factory=list,
        description="How contradictions were addressed",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Feasibility concerns",
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

    @classmethod
    def from_data(
        cls,
        data: dict,
        completeness_score: int = 0,
        rounds_completed: int = 0,
    ) -> "ClarificationOutputV2":
        """
        Factory method to create output from v2 data dict.

        Args:
            data: The data dict from ClarificationDataV2 or LLM response
            completeness_score: Final completeness score
            rounds_completed: Number of rounds completed

        Returns:
            ClarificationOutputV2 instance
        """
        return cls(
            # Tier 1
            activity_preferences=data.get("activity_preferences") or [],
            pace_preference=data.get("pace_preference"),
            tourist_vs_local=data.get("tourist_vs_local"),
            mobility_level=data.get("mobility_level"),
            dining_style=data.get("dining_style") or [],
            # Tier 2
            top_3_must_dos=data.get("top_3_must_dos"),
            transportation_mode=data.get("transportation_mode") or [],
            arrival_time=data.get("arrival_time"),
            departure_time=data.get("departure_time"),
            budget_priority=data.get("budget_priority"),
            accommodation_style=data.get("accommodation_style"),
            # Tier 3
            wifi_need=data.get("wifi_need"),
            dietary_severity=data.get("dietary_severity"),
            accessibility_needs=data.get("accessibility_needs"),
            # Tier 4
            daily_rhythm=data.get("daily_rhythm"),
            downtime_preference=data.get("downtime_preference"),
            # Meta (handle underscore-prefixed keys from LLM)
            conflicts_resolved=data.get("_conflicts_resolved")
            or data.get("conflicts_resolved")
            or [],
            warnings=data.get("_warnings") or data.get("warnings") or [],
            # Metadata
            completeness_score=completeness_score,
            rounds_completed=rounds_completed,
        )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "activity_preferences": ["nature/hiking", "adventure/adrenaline"],
                "pace_preference": "intense",
                "tourist_vs_local": "balanced",
                "mobility_level": "high (15k+/hiking)",
                "dining_style": ["street food", "casual"],
                "top_3_must_dos": {
                    "1": "Mount Batur trek",
                    "2": "Nusa Penida",
                    "3": "Beach time",
                },
                "transportation_mode": ["rental car", "walking/cycling"],
                "arrival_time": "Early AM (<9am)",
                "departure_time": "Afternoon (12-5pm)",
                "budget_priority": "experiences > comfort",
                "accommodation_style": "mid-range hotel",
                "wifi_need": "Essential (daily work)",
                "daily_rhythm": "early bird",
                "downtime_preference": "some rest",
                "conflicts_resolved": [
                    "Pace vs relaxation: chose intense days with spa evenings"
                ],
                "warnings": [
                    "Mount Batur + Nusa Penida both full-day; tight for 4 days"
                ],
                "completeness_score": 89,
                "rounds_completed": 3,
            }
        }
