"""
Typed prompt templates for the research agent.

Each sub-agent has a dedicated prompt config model and system prompt template
so prompt construction stays explicit, testable, and easy to evolve.
"""

import json
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from agents.shared.contracts.research_output_v2 import (
    AccommodationArea,
    Activity,
    CuratedHighlight,
    DiningRecommendation,
    InDestinationBudget,
    TransportOption,
    WeatherInfo,
)


def _format_optional_list(values: Optional[List[str]]) -> str:
    """Format a list for prompt interpolation."""
    return ", ".join(values) if values else "Not specified"


class BasePromptConfig(BaseModel):
    """Base class for prompt configuration models."""

    def to_prompt_context(self) -> Dict[str, str]:
        """Return prompt formatting values."""
        raise NotImplementedError

    def format_prompt(self, template: str) -> str:
        """
        Render the prompt template using this config.

        Args:
            template: Prompt template string containing named placeholders

        Returns:
            Fully rendered prompt string
        """
        return template.format(**self.to_prompt_context())


class WeatherPromptConfig(BasePromptConfig):
    """Configuration for weather research prompt generation."""

    destination: str = Field(description="Destination country or region")
    city: str = Field(description="Target city or destination unit")
    start_date: str = Field(description="Trip start date")
    end_date: str = Field(description="Trip end date")

    def to_prompt_context(self) -> Dict[str, str]:
        return {
            "destination": self.destination,
            "city": self.city,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }


class OverviewPromptConfig(BasePromptConfig):
    """Configuration for destination overview prompt generation."""

    destination: str = Field(description="Destination country or region")
    city: str = Field(description="Target city or destination unit")
    trip_duration: int = Field(description="Trip duration in days")
    travel_party: str = Field(description="Travel party descriptor")

    def to_prompt_context(self) -> Dict[str, str]:
        return {
            "destination": self.destination,
            "city": self.city,
            "trip_duration": str(self.trip_duration),
            "travel_party": self.travel_party,
        }


class BudgetPromptConfig(BasePromptConfig):
    """Configuration for budget analysis prompt generation."""

    destination: str = Field(description="Destination country or region")
    city: str = Field(description="Target city or destination unit")
    budget: float = Field(description="In-destination budget amount")
    currency: str = Field(description="Budget currency")
    trip_duration: int = Field(description="Trip duration in days")
    travel_party: str = Field(description="Travel party descriptor")
    budget_priority: Optional[str] = Field(default=None)

    def to_prompt_context(self) -> Dict[str, str]:
        return {
            "destination": self.destination,
            "city": self.city,
            "budget": f"{self.budget:.2f}",
            "currency": self.currency,
            "trip_duration": str(self.trip_duration),
            "travel_party": self.travel_party,
            "budget_priority": self.budget_priority or "Not specified",
        }


class AccommodationPromptConfig(BasePromptConfig):
    """Configuration for accommodation area recommendations."""

    destination: str = Field(description="Destination country or region")
    city: str = Field(description="Target city or destination unit")
    accommodation_style: Optional[List[str]] = Field(default=None)
    mobility_level: Optional[str] = Field(default=None)
    budget_tier: str = Field(description="Budget assessment tier")
    travel_party: str = Field(description="Travel party descriptor")

    def to_prompt_context(self) -> Dict[str, str]:
        return {
            "destination": self.destination,
            "city": self.city,
            "accommodation_style": _format_optional_list(self.accommodation_style),
            "mobility_level": self.mobility_level or "Not specified",
            "budget_tier": self.budget_tier,
            "travel_party": self.travel_party,
        }


class ActivitiesPromptConfig(BasePromptConfig):
    """Configuration for activity recommendation prompts."""

    destination: str = Field(description="Destination country or region")
    city: str = Field(description="Target city or destination unit")
    activity_preferences: Optional[List[str]] = Field(default=None)
    tourist_vs_local: Optional[str] = Field(default=None)
    pace_preference: Optional[str] = Field(default=None)
    mobility_level: Optional[str] = Field(default=None)
    must_dos: Optional[List[str]] = Field(default=None)

    def to_prompt_context(self) -> Dict[str, str]:
        return {
            "destination": self.destination,
            "city": self.city,
            "activity_preferences": _format_optional_list(self.activity_preferences),
            "tourist_vs_local": self.tourist_vs_local or "Not specified",
            "pace_preference": self.pace_preference or "Not specified",
            "mobility_level": self.mobility_level or "Not specified",
            "must_dos": _format_optional_list(self.must_dos),
        }


class DiningPromptConfig(BasePromptConfig):
    """Configuration for dining recommendation prompts."""

    destination: str = Field(description="Destination country or region")
    city: str = Field(description="Target city or destination unit")
    dining_style: Optional[List[str]] = Field(default=None)
    dietary_restrictions: Optional[str] = Field(default=None)
    budget_tier: str = Field(description="Budget assessment tier")
    travel_party: str = Field(description="Travel party descriptor")

    def to_prompt_context(self) -> Dict[str, str]:
        dietary_restrictions_line = (
            f"Dietary restrictions: {self.dietary_restrictions}"
            if self.dietary_restrictions
            else "No dietary restrictions."
        )
        return {
            "destination": self.destination,
            "city": self.city,
            "dining_style": _format_optional_list(self.dining_style),
            "dietary_restrictions_line": dietary_restrictions_line,
            "budget_tier": self.budget_tier,
            "travel_party": self.travel_party,
        }


class TransportPromptConfig(BasePromptConfig):
    """Configuration for transportation recommendation prompts."""

    destination: str = Field(description="Destination country or region")
    city: str = Field(description="Target city or destination unit")
    mobility_level: Optional[str] = Field(default=None)
    budget_tier: str = Field(description="Budget assessment tier")
    trip_duration: int = Field(description="Trip duration in days")

    def to_prompt_context(self) -> Dict[str, str]:
        return {
            "destination": self.destination,
            "city": self.city,
            "mobility_level": self.mobility_level or "Not specified",
            "budget_tier": self.budget_tier,
            "trip_duration": str(self.trip_duration),
        }


class HighlightsPromptConfig(BasePromptConfig):
    """Configuration for curated highlights prompt generation."""

    destination: str = Field(description="Destination country or region")
    city: str = Field(description="Target city or destination unit")
    must_dos: Optional[List[str]] = Field(default=None)
    activity_preferences: Optional[List[str]] = Field(default=None)
    activities_json: str = Field(description="Serialized activity results")
    dining_json: str = Field(description="Serialized dining results")
    overview: Optional[str] = Field(default=None)

    def to_prompt_context(self) -> Dict[str, str]:
        return {
            "destination": self.destination,
            "city": self.city,
            "must_dos": _format_optional_list(self.must_dos),
            "activity_preferences": _format_optional_list(self.activity_preferences),
            "activities_json": self.activities_json,
            "dining_json": self.dining_json,
            "overview": self.overview or "Not available",
        }


class DestinationOverviewOutput(BaseModel):
    """Structured output wrapper for destination overview generation."""

    city_name: Optional[str] = Field(default=None, description="Resolved city name")
    country: Optional[str] = Field(default=None, description="Resolved country name")
    overview: str = Field(description="Destination overview tailored to the traveler")
    recommended_days: int = Field(
        ge=1, description="Recommended number of days for this city"
    )


class AccommodationAreasOutput(BaseModel):
    """Structured output wrapper for accommodation recommendations."""

    items: List[AccommodationArea] = Field(
        default_factory=list, description="Accommodation area recommendations"
    )


class ActivitiesOutput(BaseModel):
    """Structured output wrapper for activities."""

    items: List[Activity] = Field(
        default_factory=list, description="Activity recommendations"
    )


class DiningOutput(BaseModel):
    """Structured output wrapper for dining recommendations."""

    items: List[DiningRecommendation] = Field(
        default_factory=list, description="Dining recommendations"
    )


class TransportOutput(BaseModel):
    """Structured output wrapper for transportation recommendations."""

    items: List[TransportOption] = Field(
        default_factory=list, description="Transportation recommendations"
    )


class HighlightsOutput(BaseModel):
    """Structured output wrapper for curated highlights."""

    items: List[CuratedHighlight] = Field(
        default_factory=list, description="Ranked curated highlights"
    )


WEATHER_SYSTEM_PROMPT_TEMPLATE = """# Role
You are a travel research sub-agent responsible only for trip-weather guidance.

Produce structured output for {city}, {destination} covering the travel window from {start_date} to {end_date}.
Use current seasonal norms, not exact live forecasts.

# Requirements
- Derive the season from the travel window for the correct hemisphere.
- Output season as exactly one of: spring, summer, autumn, winter.
- Focus on conditions relevant to trip planning.
- Temperature range must be in Celsius.
- Weather notes should be practical and concise.
- Clothing recommendations should reflect likely conditions.
- Do not mention uncertainty excessively.
- Use an object for temperature_range_celsius with numeric min and max keys.
- Use arrays for clothing_recommendations and weather_notes, even if there is only one item.

# Output
Return content that matches the WeatherInfo schema exactly.
"""


OVERVIEW_SYSTEM_PROMPT_TEMPLATE = """# Role
You are a travel research sub-agent responsible only for destination overview synthesis.

Produce a concise overview for {city}, {destination} tailored to a {travel_party} trip lasting {trip_duration} days.

# Requirements
- Summarize what makes the destination distinctive for itinerary planning.
- Keep the overview specific, not generic tourism copy.
- Set recommended_days realistically for the destination unit being described.
- Resolve city_name and country explicitly when possible.

# Output
Return content that matches the DestinationOverviewOutput schema exactly.
"""


BUDGET_SYSTEM_PROMPT_TEMPLATE = """# Role
You are a travel budget research sub-agent.

The traveler is going to {city}, {destination}.
The user's budget of {budget} {currency} is their IN-DESTINATION spending budget only.
This amount covers accommodation, food, activities, and local transport for {trip_duration} days.
Flights, visas, travel insurance, and pre-trip purchases are already handled separately.
Allocate this full {budget} {currency} across the four in-destination categories.

# Trip Context
- Travel party: {travel_party}
- Budget priority: {budget_priority}

# Requirements
- Account for destination purchasing power when assessing realism and category allocation.
- Convert the result to USD if needed for the schema.
- Produce a realistic daily budget.
- Ensure the category breakdown sums to total_available_usd.
- Budget tips should be concrete and traveler-relevant.
- Include trip_duration_days and daily_budget_usd explicitly.
- Use an object for breakdown with the keys accommodation, food, activities, and local_transport.
- budget_assessment must be exactly one of: tight, comfortable, generous.
- budget_tips must be an array, even if there is only one tip.

# Output
Return content that matches the InDestinationBudget schema exactly.
"""


ACCOMMODATION_SYSTEM_PROMPT_TEMPLATE = """# Role
You are a lodging research sub-agent.

Recommend accommodation areas for {city}, {destination}.

# Traveler Context
- Travel party: {travel_party}
- Preferred accommodation styles: {accommodation_style}
- Mobility level: {mobility_level}
- Budget tier: {budget_tier}

# Requirements
- Recommend neighborhoods or districts, not specific hotels.
- Explain why each area suits this traveler profile.
- Balance convenience, atmosphere, and cost.
- Include clear pros and cons for each area.

# Output
Return content that matches the AccommodationAreasOutput schema exactly.
"""


ACTIVITIES_SYSTEM_PROMPT_TEMPLATE = """# Role
You are an activities research sub-agent.

Recommend concrete activities for {city}, {destination}.

# Traveler Context
- Activity preferences: {activity_preferences}
- Tourist vs local preference: {tourist_vs_local}
- Pace preference: {pace_preference}
- Mobility level: {mobility_level}
- Must-dos: {must_dos}

# Requirements
- Recommend specific, real activities or attractions.
- Match recommendations to stated preferences and constraints.
- Mix iconic and aligned picks based on the tourist/local preference.
- Include timing, estimated duration, and cost where useful.
- Assign each activity a neighborhood or district name so the planner can group nearby stops.
- Set travel_time_from_centre_mins as the approximate travel time from the central accommodation zone in {city}.

# Output
Return content that matches the ActivitiesOutput schema exactly.
"""


DINING_SYSTEM_PROMPT_TEMPLATE = """# Role
You are a dining research sub-agent.

Recommend dining options for {city}, {destination}.

# Traveler Context
- Dining style: {dining_style}
- Budget tier: {budget_tier}
- Travel party: {travel_party}
{dietary_restrictions_line}

# Requirements
- Recommend specific, real dining venues or food markets when possible.
- Ensure recommendations respect stated dietary needs.
- Vary the recommendations across meal types or use cases.
- Include must-try dishes where relevant.

# Output
Return content that matches the DiningOutput schema exactly.
"""


TRANSPORT_SYSTEM_PROMPT_TEMPLATE = """# Role
You are a local transportation research sub-agent.

Recommend transport options for navigating {city}, {destination}.

# Traveler Context
- Mobility level: {mobility_level}
- Budget tier: {budget_tier}
- Trip duration: {trip_duration} days

# Requirements
- Focus on practical local transport inside the destination.
- Include cost, coverage, and actionable usage tips.
- Prioritize options appropriate for the traveler's mobility and budget.

# Output
Return content that matches the TransportOutput schema exactly.
"""


HIGHLIGHTS_SYSTEM_PROMPT_TEMPLATE = """# Role
You are a synthesis sub-agent creating the final ranked highlights shortlist for the planner.

Produce curated highlights for {city}, {destination}.

# Traveler Context
- Must-dos: {must_dos}
- Activity preferences: {activity_preferences}
- Destination overview: {overview}

# Upstream Research
Activities JSON:
{activities_json}

Dining JSON:
{dining_json}

# Requirements
- Rank the most planner-useful highlights across activities and dining.
- Prioritize items that clearly fit the traveler profile.
- Include a mix of signature experiences, dining, and hidden gems when supported.
- Avoid repeating generic statements already covered in the overview.
- Return between 6 and 10 highlights.
- Each title must exactly match the source item name from the activity or dining input.
- Include at least 2 dining highlights.
- Include at least 1 hidden_gem highlight.
- category must be exactly one of: experience, dining, hidden_gem.

# Output
Return content that matches the HighlightsOutput schema exactly.
"""


def build_json_context(value: object) -> str:
    """Serialize a value for safe prompt embedding."""
    return json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True)


__all__ = [
    "WeatherPromptConfig",
    "OverviewPromptConfig",
    "BudgetPromptConfig",
    "AccommodationPromptConfig",
    "ActivitiesPromptConfig",
    "DiningPromptConfig",
    "TransportPromptConfig",
    "HighlightsPromptConfig",
    "DestinationOverviewOutput",
    "AccommodationAreasOutput",
    "ActivitiesOutput",
    "DiningOutput",
    "TransportOutput",
    "HighlightsOutput",
    "WEATHER_SYSTEM_PROMPT_TEMPLATE",
    "OVERVIEW_SYSTEM_PROMPT_TEMPLATE",
    "BUDGET_SYSTEM_PROMPT_TEMPLATE",
    "ACCOMMODATION_SYSTEM_PROMPT_TEMPLATE",
    "ACTIVITIES_SYSTEM_PROMPT_TEMPLATE",
    "DINING_SYSTEM_PROMPT_TEMPLATE",
    "TRANSPORT_SYSTEM_PROMPT_TEMPLATE",
    "HIGHLIGHTS_SYSTEM_PROMPT_TEMPLATE",
    "build_json_context",
    "WeatherInfo",
    "InDestinationBudget",
]
