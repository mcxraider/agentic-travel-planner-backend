"""
Research agent output contract v2.

Defines the richer structured output that the future multi-node research
pipeline will produce for downstream planner consumption.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


SectionStatus = Literal["ok", "missing", "critical_failure"]


def _normalize_string_list(value: Any) -> List[str]:
    """
    Normalize a string-or-list value into a list of strings.

    Args:
        value: Arbitrary incoming value from LLM JSON output

    Returns:
        Clean list of non-empty strings
    """
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []

    cleaned = str(value).strip()
    return [cleaned] if cleaned else []


def _normalize_precipitation_likelihood(value: Any) -> str:
    """
    Normalize precipitation labels to the supported enum.

    Args:
        value: Arbitrary incoming precipitation value

    Returns:
        One of ``low``, ``moderate``, or ``high``
    """
    normalized = str(value or "").strip().lower()
    if normalized in {"low", "moderate", "high"}:
        return normalized
    if any(token in normalized for token in ("storm", "downpour", "heavy", "frequent")):
        return "high"
    if any(token in normalized for token in ("dry", "minimal", "rare", "light")):
        return "low"
    return "moderate"


def _normalize_budget_assessment(
    value: Any,
    *,
    total_available_usd: Any,
    daily_budget_usd: Any,
    trip_duration_days: Any,
) -> str:
    """
    Normalize or derive the budget assessment enum.

    Args:
        value: Incoming assessment value from the model
        total_available_usd: Total available budget
        daily_budget_usd: Daily budget if supplied
        trip_duration_days: Trip duration if supplied

    Returns:
        One of ``tight``, ``comfortable``, or ``generous``
    """
    normalized = str(value or "").strip().lower()
    if normalized in {"tight", "comfortable", "generous"}:
        return normalized
    if "tight" in normalized:
        return "tight"
    if "comfortable" in normalized:
        return "comfortable"
    if "generous" in normalized or "luxury" in normalized:
        return "generous"

    if daily_budget_usd is None:
        try:
            total_budget = float(total_available_usd)
            duration = max(int(trip_duration_days), 1)
            daily_budget_usd = total_budget / duration
        except (TypeError, ValueError):
            return "comfortable"

    try:
        daily_budget = float(daily_budget_usd)
    except (TypeError, ValueError):
        return "comfortable"

    if daily_budget < 100:
        return "tight"
    if daily_budget < 250:
        return "comfortable"
    return "generous"


def _first_present(*values: Any) -> Any:
    """
    Return the first value that is not ``None``.

    Args:
        *values: Candidate values

    Returns:
        First non-``None`` value, or ``None`` if all are missing
    """
    for value in values:
        if value is not None:
            return value
    return None


class TemperatureRangeCelsius(BaseModel):
    """Minimum and maximum expected temperatures in Celsius."""

    min: float = Field(description="Expected minimum temperature in Celsius")
    max: float = Field(description="Expected maximum temperature in Celsius")


class WeatherInfo(BaseModel):
    """Seasonal weather summary for the destination."""

    season: str = Field(description="Season during the trip window")
    temperature_range_celsius: TemperatureRangeCelsius = Field(
        description="Temperature range in Celsius with min and max values",
    )
    precipitation_likelihood: Literal["low", "moderate", "high"] = Field(
        description="Expected precipitation level during the trip"
    )
    daylight_hours: Optional[float] = Field(
        default=None, description="Approximate hours of daylight"
    )
    clothing_recommendations: List[str] = Field(
        default_factory=list,
        description="Packing or clothing guidance based on expected weather",
    )
    weather_notes: List[str] = Field(
        default_factory=list,
        description="Additional weather-specific planning notes",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_weather_fields(cls, value: Any) -> Any:
        """
        Normalize common JSON-mode variations before validation.

        Args:
            value: Incoming raw weather payload

        Returns:
            Normalized payload ready for validation
        """
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        normalized["season"] = str(normalized.get("season") or "not specified").strip()
        normalized["precipitation_likelihood"] = _normalize_precipitation_likelihood(
            normalized.get("precipitation_likelihood")
        )
        normalized["clothing_recommendations"] = _normalize_string_list(
            normalized.get("clothing_recommendations")
        )
        normalized["weather_notes"] = _normalize_string_list(
            normalized.get("weather_notes")
        )
        return normalized


class AccommodationArea(BaseModel):
    """Recommended neighborhood or area for staying."""

    neighborhood: str = Field(description="Neighborhood or district name")
    description: str = Field(description="Short summary of the area")
    why_suitable: str = Field(
        description="Why this area fits the user's budget, party, and constraints"
    )
    price_tier: Literal["budget", "mid-range", "luxury"] = Field(
        description="Relative accommodation price tier"
    )
    pros: List[str] = Field(
        default_factory=list, description="Reasons to choose this area"
    )
    cons: List[str] = Field(
        default_factory=list, description="Tradeoffs or downsides of this area"
    )


class Activity(BaseModel):
    """Destination activity recommendation."""

    name: str = Field(description="Specific real-world activity or attraction name")
    category: str = Field(description="High-level activity category")
    description: str = Field(description="Short description of the activity")
    estimated_duration_hours: float = Field(
        ge=0, description="Typical time required in hours"
    )
    estimated_cost_usd: Optional[float] = Field(
        default=None, description="Estimated cost in USD if known"
    )
    best_time_to_visit: Optional[str] = Field(
        default=None, description="Best timing for the activity"
    )
    booking_required: bool = Field(
        description="Whether advance booking is recommended or required"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Preference-matching tags for downstream planning",
    )


class DiningRecommendation(BaseModel):
    """Dining recommendation for the destination."""

    name: str = Field(description="Restaurant, market, or dining venue name")
    cuisine_type: str = Field(description="Cuisine or dining style")
    description: str = Field(description="Short description of the dining spot")
    price_tier: Literal["budget", "mid-range", "fine-dining"] = Field(
        description="Relative dining cost tier"
    )
    estimated_cost_per_person_usd: Optional[float] = Field(
        default=None, description="Estimated per-person cost in USD"
    )
    must_try_dishes: List[str] = Field(
        default_factory=list, description="Signature dishes to try"
    )
    neighborhood: Optional[str] = Field(
        default=None, description="Neighborhood or district if known"
    )
    best_for: str = Field(
        description="Best meal or use case, e.g. breakfast, lunch, dinner, any"
    )


class TransportOption(BaseModel):
    """Transportation option for getting around the destination."""

    mode: str = Field(description="Transport mode")
    description: str = Field(description="How and when to use this transport option")
    estimated_daily_cost_usd: Optional[float] = Field(
        default=None, description="Approximate daily cost in USD"
    )
    coverage: str = Field(description="Where or how broadly this mode is useful")
    tips: List[str] = Field(
        default_factory=list, description="Practical advice for using this mode"
    )


class CuratedHighlight(BaseModel):
    """Ranked high-signal recommendation synthesized across research outputs."""

    rank: int = Field(ge=1, description="Relative priority ranking")
    category: Literal["experience", "dining", "hidden_gem"] = Field(
        description="Highlight category"
    )
    title: str = Field(description="Short highlight title")
    why_it_matters: str = Field(
        description="Why this highlight matters for this specific traveler profile"
    )
    estimated_duration_hours: Optional[float] = Field(
        default=None, description="Approximate duration in hours if applicable"
    )
    estimated_cost_usd: Optional[float] = Field(
        default=None, description="Approximate cost in USD if known"
    )


class BudgetBreakdown(BaseModel):
    """Budget breakdown across core in-destination spending categories."""

    accommodation: float = Field(description="Accommodation budget in USD")
    food: float = Field(description="Food budget in USD")
    activities: float = Field(description="Activities budget in USD")
    local_transport: float = Field(description="Local transport budget in USD")


class InDestinationBudget(BaseModel):
    """Budget analysis scoped to in-destination spending only."""

    total_available_usd: float = Field(
        description="Trip budget available for in-destination spending"
    )
    trip_duration_days: int = Field(ge=1, description="Trip duration in days")
    daily_budget_usd: float = Field(description="Average daily budget in USD")
    breakdown: BudgetBreakdown = Field(
        description="Budget breakdown by category",
    )
    budget_assessment: Literal["tight", "comfortable", "generous"] = Field(
        description="Overall budget fit assessment"
    )
    budget_tips: List[str] = Field(
        default_factory=list,
        description="Budget optimization advice for the traveler",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_budget_fields(cls, value: Any) -> Any:
        """
        Normalize common JSON-mode variations before validation.

        Args:
            value: Incoming raw budget payload

        Returns:
            Normalized payload ready for validation
        """
        if not isinstance(value, dict):
            return value

        normalized = dict(value)

        if (
            normalized.get("trip_duration_days") is None
            and normalized.get("trip_duration") is not None
        ):
            normalized["trip_duration_days"] = normalized.get("trip_duration")

        if normalized.get("total_available_usd") is None:
            for alias in ("total_budget_usd", "budget_usd", "budget"):
                if normalized.get(alias) is not None:
                    normalized["total_available_usd"] = normalized.get(alias)
                    break

        if normalized.get("daily_budget_usd") is None:
            try:
                total_budget = float(normalized["total_available_usd"])
                duration = max(int(normalized["trip_duration_days"]), 1)
                normalized["daily_budget_usd"] = round(total_budget / duration, 2)
            except (KeyError, TypeError, ValueError):
                pass

        normalized["budget_assessment"] = _normalize_budget_assessment(
            normalized.get("budget_assessment"),
            total_available_usd=normalized.get("total_available_usd"),
            daily_budget_usd=normalized.get("daily_budget_usd"),
            trip_duration_days=normalized.get("trip_duration_days"),
        )
        normalized["budget_tips"] = _normalize_string_list(
            normalized.get("budget_tips")
        )

        breakdown = normalized.get("breakdown")
        if breakdown is None:
            breakdown = {
                "accommodation": normalized.get("accommodation_budget_usd"),
                "food": normalized.get("food_budget_usd"),
                "activities": normalized.get("activities_budget_usd"),
                "local_transport": normalized.get("local_transport_budget_usd"),
            }

        if isinstance(breakdown, dict):
            normalized["breakdown"] = {
                "accommodation": _first_present(
                    breakdown.get("accommodation"),
                    breakdown.get("lodging"),
                    breakdown.get("stay"),
                ),
                "food": _first_present(
                    breakdown.get("food"),
                    breakdown.get("dining"),
                    breakdown.get("meals"),
                ),
                "activities": _first_present(
                    breakdown.get("activities"),
                    breakdown.get("sightseeing"),
                    breakdown.get("experiences"),
                ),
                "local_transport": _first_present(
                    breakdown.get("local_transport"),
                    breakdown.get("transport"),
                    breakdown.get("transportation"),
                ),
            }

        normalized_breakdown = normalized.get("breakdown")
        if isinstance(normalized_breakdown, dict):
            populated_values = [
                value for value in normalized_breakdown.values() if value is not None
            ]
            if (
                not populated_values
                and normalized.get("total_available_usd") is not None
            ):
                try:
                    total_budget = float(normalized["total_available_usd"])
                    normalized["breakdown"] = {
                        "accommodation": round(total_budget * 0.4, 2),
                        "food": round(total_budget * 0.25, 2),
                        "activities": round(total_budget * 0.25, 2),
                        "local_transport": round(total_budget * 0.1, 2),
                    }
                except (TypeError, ValueError):
                    pass

        return normalized


class CityResearchV2(BaseModel):
    """Research content for a city or city-like destination unit."""

    city_name: Optional[str] = Field(
        default=None, description="Primary city name if resolved"
    )
    country: Optional[str] = Field(default=None, description="Country name if resolved")
    destination_overview: Optional[str] = Field(
        default=None, description="Short city or destination overview"
    )
    recommended_days: Optional[int] = Field(
        default=None, ge=1, description="Suggested number of days for this city"
    )
    weather: Optional[WeatherInfo] = Field(
        default=None, description="Weather guidance for this city"
    )
    accommodation_areas: List[AccommodationArea] = Field(
        default_factory=list,
        description="Recommended accommodation neighborhoods",
    )
    activities: List[Activity] = Field(
        default_factory=list, description="Recommended activities"
    )
    dining: List[DiningRecommendation] = Field(
        default_factory=list, description="Dining recommendations"
    )


class ResearchMetadata(BaseModel):
    """Metadata describing research completeness and degradation status."""

    generated_at: str = Field(description="ISO timestamp when the output was built")
    session_id: Optional[str] = Field(
        default=None, description="Session identifier for traceability"
    )
    degraded: bool = Field(
        default=False,
        description="Whether any section is missing or failed during research",
    )
    missing_sections: List[str] = Field(
        default_factory=list,
        description="Sections that were unavailable in the final output",
    )
    critical_failures: List[str] = Field(
        default_factory=list,
        description="Critical sections that failed and forced degraded mode",
    )
    section_status: Dict[str, SectionStatus] = Field(
        default_factory=dict,
        description="Per-section status map for downstream inspection",
    )


class ResearchOutputV2(BaseModel):
    """Contract for the Stage 1 research agent v2 output shape."""

    destination: str = Field(description="Trip destination")
    trip_duration_days: int = Field(ge=1, description="Trip duration in days")
    travel_party: str = Field(description="Travel party descriptor")
    cities: List[CityResearchV2] = Field(
        default_factory=list,
        description="Per-city research output",
    )
    transportation: List[TransportOption] = Field(
        default_factory=list,
        description="Destination transportation options",
    )
    curated_highlights: List[CuratedHighlight] = Field(
        default_factory=list,
        description="Cross-section ranked highlights for the planner",
    )
    budget_analysis: Optional[InDestinationBudget] = Field(
        default=None,
        description="Budget analysis for in-destination spending",
    )
    metadata: ResearchMetadata = Field(
        description="Completeness and generation metadata"
    )


__all__ = [
    "SectionStatus",
    "TemperatureRangeCelsius",
    "WeatherInfo",
    "AccommodationArea",
    "Activity",
    "DiningRecommendation",
    "TransportOption",
    "CuratedHighlight",
    "BudgetBreakdown",
    "InDestinationBudget",
    "CityResearchV2",
    "ResearchMetadata",
    "ResearchOutputV2",
]
