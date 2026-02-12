"""
Research agent output contract.

Defines the structured output that the research agent produces
for consumption by the planner agent.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class PointOfInterest(BaseModel):
    """A single point of interest within a city."""

    name: str = Field(description="Name of the POI")
    category: str = Field(
        description="Category (e.g., 'temple', 'restaurant', 'beach', 'museum')"
    )
    description: str = Field(description="Brief description of the POI")
    estimated_duration_hours: float = Field(
        ge=0.5, description="Estimated visit duration in hours"
    )
    cost_estimate_usd: Optional[float] = Field(
        default=None, description="Estimated cost in USD (None if free)"
    )
    rating: Optional[float] = Field(
        default=None, ge=0, le=5, description="Rating out of 5"
    )
    tags: List[str] = Field(
        default_factory=list, description="Tags for matching preferences"
    )
    address: Optional[str] = Field(default=None, description="Location address")
    opening_hours: Optional[str] = Field(
        default=None, description="Opening hours info"
    )


class CityResearch(BaseModel):
    """Research data for a single city."""

    city_name: str = Field(description="Name of the city")
    country: str = Field(description="Country the city is in")
    description: str = Field(description="Brief city overview")
    recommended_days: int = Field(
        ge=1, description="Recommended number of days to spend"
    )
    pois: List[PointOfInterest] = Field(
        default_factory=list, description="Points of interest in this city"
    )


class TransportOption(BaseModel):
    """A transport option between locations."""

    mode: str = Field(description="Transport mode (e.g., 'taxi', 'bus', 'train')")
    description: str = Field(description="Description of the transport option")
    estimated_cost_usd: Optional[float] = Field(
        default=None, description="Estimated cost in USD"
    )
    estimated_duration_minutes: Optional[int] = Field(
        default=None, description="Estimated travel time in minutes"
    )


class LogisticsInfo(BaseModel):
    """Logistics and practical travel information."""

    local_currency: str = Field(description="Local currency code")
    exchange_rate_to_usd: Optional[float] = Field(
        default=None, description="Exchange rate: 1 USD = X local currency"
    )
    language: str = Field(description="Primary local language")
    timezone: str = Field(description="Timezone (e.g., 'Asia/Bali')")
    transport_options: List[TransportOption] = Field(
        default_factory=list, description="Available transport options"
    )
    safety_notes: List[str] = Field(
        default_factory=list, description="Safety tips and notes"
    )
    connectivity_notes: Optional[str] = Field(
        default=None, description="WiFi/data connectivity info"
    )


class BudgetAnalysis(BaseModel):
    """Budget breakdown and analysis."""

    total_budget_usd: float = Field(description="Total budget in USD")
    estimated_accommodation_per_night_usd: float = Field(
        description="Estimated nightly accommodation cost"
    )
    estimated_food_per_day_usd: float = Field(
        description="Estimated daily food cost"
    )
    estimated_transport_per_day_usd: float = Field(
        description="Estimated daily transport cost"
    )
    estimated_activities_per_day_usd: float = Field(
        description="Estimated daily activities cost"
    )
    budget_assessment: str = Field(
        description="Assessment: 'tight', 'comfortable', or 'generous'"
    )


class ResearchOutputV1(BaseModel):
    """
    Contract for research agent output (v1).

    This model defines the structured research data that flows from
    the research agent to the planner agent.
    """

    destination: str = Field(description="Trip destination")
    cities: List[CityResearch] = Field(
        default_factory=list, description="Research data per city"
    )
    logistics: LogisticsInfo = Field(description="Logistics and practical info")
    budget_analysis: BudgetAnalysis = Field(description="Budget breakdown")
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional metadata (e.g., data_source, generated_at)",
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "destination": "Bali, Indonesia",
                "cities": [
                    {
                        "city_name": "Ubud",
                        "country": "Indonesia",
                        "description": "Cultural heart of Bali",
                        "recommended_days": 2,
                        "pois": [
                            {
                                "name": "Tegallalang Rice Terrace",
                                "category": "nature",
                                "description": "Iconic terraced rice paddies",
                                "estimated_duration_hours": 2.0,
                                "cost_estimate_usd": 5.0,
                                "rating": 4.5,
                                "tags": ["nature", "photography", "hiking"],
                            }
                        ],
                    }
                ],
                "logistics": {
                    "local_currency": "IDR",
                    "exchange_rate_to_usd": 15500.0,
                    "language": "Indonesian",
                    "timezone": "Asia/Makassar",
                    "transport_options": [
                        {
                            "mode": "scooter rental",
                            "description": "Most popular local transport",
                            "estimated_cost_usd": 5.0,
                            "estimated_duration_minutes": None,
                        }
                    ],
                    "safety_notes": ["Beware of traffic on narrow roads"],
                },
                "budget_analysis": {
                    "total_budget_usd": 1500.0,
                    "estimated_accommodation_per_night_usd": 50.0,
                    "estimated_food_per_day_usd": 20.0,
                    "estimated_transport_per_day_usd": 10.0,
                    "estimated_activities_per_day_usd": 25.0,
                    "budget_assessment": "comfortable",
                },
            }
        }
