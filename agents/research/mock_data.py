"""
Mock data generator for the research agent.

Generates hardcoded but contextually aware research data
for testing the pipeline without LLM calls.
"""

from typing import List, Optional
from datetime import datetime

from agents.shared.contracts.research_output import (
    ResearchOutputV1,
    CityResearch,
    PointOfInterest,
    LogisticsInfo,
    TransportOption,
    BudgetAnalysis,
)


# Default POIs by category for generic destinations
_DEFAULT_POIS = {
    "temple": PointOfInterest(
        name="Grand Temple",
        category="temple",
        description="Historic temple with stunning architecture",
        estimated_duration_hours=2.0,
        cost_estimate_usd=5.0,
        rating=4.5,
        tags=["culture", "history", "photography"],
        opening_hours="08:00-17:00",
    ),
    "market": PointOfInterest(
        name="Central Market",
        category="market",
        description="Vibrant local market with street food and crafts",
        estimated_duration_hours=1.5,
        cost_estimate_usd=0.0,
        rating=4.2,
        tags=["food", "shopping", "local"],
    ),
    "nature": PointOfInterest(
        name="Scenic Viewpoint Trail",
        category="nature",
        description="Moderate hiking trail with panoramic views",
        estimated_duration_hours=3.0,
        cost_estimate_usd=0.0,
        rating=4.7,
        tags=["nature", "hiking", "photography"],
    ),
    "beach": PointOfInterest(
        name="Crystal Beach",
        category="beach",
        description="Beautiful white sand beach with clear waters",
        estimated_duration_hours=3.0,
        cost_estimate_usd=0.0,
        rating=4.6,
        tags=["beach", "relaxation", "swimming"],
    ),
    "restaurant": PointOfInterest(
        name="Local Flavors Restaurant",
        category="restaurant",
        description="Highly rated local cuisine restaurant",
        estimated_duration_hours=1.5,
        cost_estimate_usd=15.0,
        rating=4.4,
        tags=["food", "dining", "local"],
    ),
    "museum": PointOfInterest(
        name="National Museum",
        category="museum",
        description="Comprehensive museum covering local history and art",
        estimated_duration_hours=2.5,
        cost_estimate_usd=10.0,
        rating=4.3,
        tags=["culture", "history", "museum"],
    ),
}


def _generate_city_pois(
    city_name: str,
    activity_preferences: Optional[List[str]] = None,
) -> List[PointOfInterest]:
    """
    Generate POIs for a city based on activity preferences.

    Args:
        city_name: Name of the city
        activity_preferences: User's activity preferences for filtering

    Returns:
        List of PointOfInterest objects
    """
    pois = []

    # Always include core POIs
    for category, poi in _DEFAULT_POIS.items():
        # Create a city-specific copy
        city_poi = poi.model_copy(
            update={"name": f"{city_name} {poi.name}"}
        )
        pois.append(city_poi)

    return pois


def _generate_transport_options(destination: str) -> List[TransportOption]:
    """Generate transport options for a destination."""
    return [
        TransportOption(
            mode="taxi/rideshare",
            description="Widely available taxis and rideshare apps",
            estimated_cost_usd=10.0,
            estimated_duration_minutes=30,
        ),
        TransportOption(
            mode="public transit",
            description="Local bus and metro system",
            estimated_cost_usd=2.0,
            estimated_duration_minutes=45,
        ),
        TransportOption(
            mode="walking",
            description="Walk between nearby attractions",
            estimated_cost_usd=0.0,
            estimated_duration_minutes=20,
        ),
    ]


def _calculate_budget_assessment(
    budget: float, trip_duration: int, travel_party: str
) -> str:
    """Determine budget assessment based on daily budget."""
    # Simple heuristic: daily budget per person
    daily_budget = budget / max(trip_duration, 1)
    if daily_budget < 80:
        return "tight"
    elif daily_budget < 200:
        return "comfortable"
    else:
        return "generous"


def generate_mock_research(
    destination: str,
    destination_cities: Optional[List[str]],
    trip_duration: int,
    budget: float,
    currency: str,
    travel_party: str,
    activity_preferences: Optional[List[str]] = None,
    accommodation_style: Optional[List[str]] = None,
) -> ResearchOutputV1:
    """
    Generate mock research data for a destination.

    Produces contextually aware but hardcoded research output
    for end-to-end pipeline testing.

    Args:
        destination: Trip destination
        destination_cities: Specific cities to research
        trip_duration: Trip duration in days
        budget: Trip budget
        currency: Budget currency
        travel_party: Travel party description
        activity_preferences: User's activity preferences
        accommodation_style: User's accommodation preferences

    Returns:
        ResearchOutputV1 with populated mock data
    """
    # Determine cities to research
    cities_to_research = destination_cities or [destination.split(",")[0].strip()]

    # Distribute days across cities
    days_per_city = max(1, trip_duration // len(cities_to_research))

    # Generate city research
    cities = []
    for city_name in cities_to_research:
        city = CityResearch(
            city_name=city_name,
            country=destination.split(",")[-1].strip() if "," in destination else destination,
            description=f"A vibrant destination in {destination} with diverse attractions",
            recommended_days=days_per_city,
            pois=_generate_city_pois(city_name, activity_preferences),
        )
        cities.append(city)

    # Generate logistics
    logistics = LogisticsInfo(
        local_currency=currency if currency != "USD" else "Local Currency",
        exchange_rate_to_usd=1.0,
        language="Local language",
        timezone="Local timezone",
        transport_options=_generate_transport_options(destination),
        safety_notes=[
            "Keep valuables secure in crowded areas",
            "Use registered taxis or rideshare apps",
            "Stay hydrated and use sunscreen",
        ],
        connectivity_notes="WiFi available at most hotels and cafes",
    )

    # Budget analysis
    budget_usd = budget  # Simplified: assume USD for mock
    accommodation_per_night = budget_usd * 0.35 / max(trip_duration, 1)
    food_per_day = budget_usd * 0.20 / max(trip_duration, 1)
    transport_per_day = budget_usd * 0.10 / max(trip_duration, 1)
    activities_per_day = budget_usd * 0.15 / max(trip_duration, 1)

    budget_analysis = BudgetAnalysis(
        total_budget_usd=budget_usd,
        estimated_accommodation_per_night_usd=round(accommodation_per_night, 2),
        estimated_food_per_day_usd=round(food_per_day, 2),
        estimated_transport_per_day_usd=round(transport_per_day, 2),
        estimated_activities_per_day_usd=round(activities_per_day, 2),
        budget_assessment=_calculate_budget_assessment(
            budget_usd, trip_duration, travel_party
        ),
    )

    return ResearchOutputV1(
        destination=destination,
        cities=cities,
        logistics=logistics,
        budget_analysis=budget_analysis,
        metadata={
            "data_source": "mock",
            "generated_at": datetime.utcnow().isoformat(),
            "version": "v1",
        },
    )
