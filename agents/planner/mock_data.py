"""
Mock data generator for the planner agent.

Generates a hardcoded but contextually aware day-by-day itinerary
for testing the pipeline without LLM calls.
"""

from typing import List, Optional
from datetime import datetime, timedelta

from agents.shared.contracts.planner_output import (
    PlannerOutputV1,
    ItineraryDay,
    ItineraryEvent,
    CostSummary,
)


# Daily event templates by time slot
_MORNING_EVENTS = [
    ("Breakfast at Local Cafe", "dining", 1.0, 8.0),
    ("Morning Market Visit", "activity", 1.5, 0.0),
    ("Sunrise Viewpoint", "activity", 2.0, 5.0),
]

_MIDDAY_EVENTS = [
    ("Cultural Site Visit", "activity", 2.5, 10.0),
    ("Guided Walking Tour", "activity", 2.0, 15.0),
    ("Museum Exploration", "activity", 2.0, 10.0),
]

_LUNCH_EVENTS = [
    ("Lunch at Local Restaurant", "dining", 1.0, 12.0),
    ("Street Food Tour", "dining", 1.5, 8.0),
]

_AFTERNOON_EVENTS = [
    ("Neighborhood Exploration", "activity", 2.0, 0.0),
    ("Nature Walk", "leisure", 2.0, 0.0),
    ("Shopping & Local Crafts", "activity", 1.5, 20.0),
    ("Beach Time", "leisure", 2.5, 0.0),
]

_DINNER_EVENTS = [
    ("Dinner at Recommended Restaurant", "dining", 1.5, 20.0),
    ("Evening Food Market", "dining", 1.5, 10.0),
]


def _generate_day_events(
    day_number: int,
    city: str,
    pace_preference: Optional[str] = None,
    is_arrival_day: bool = False,
    is_departure_day: bool = False,
) -> List[ItineraryEvent]:
    """
    Generate events for a single day.

    Args:
        day_number: Day number in the itinerary
        city: City for this day
        pace_preference: User's pace preference
        is_arrival_day: Whether this is the first day
        is_departure_day: Whether this is the last day

    Returns:
        List of ItineraryEvent objects
    """
    events = []
    event_counter = 1

    # Use modulo to vary events across days
    day_idx = (day_number - 1) % 3

    # Morning
    if not is_arrival_day:
        title, category, duration, cost = _MORNING_EVENTS[day_idx]
        events.append(ItineraryEvent(
            event_id=f"d{day_number}_e{event_counter}",
            time_slot="08:00-09:00",
            title=title,
            description=f"{title} in {city}",
            category=category,
            location=city,
            estimated_cost_usd=cost,
            duration_hours=duration,
        ))
        event_counter += 1

    # Mid-morning activity
    if not is_departure_day:
        title, category, duration, cost = _MIDDAY_EVENTS[day_idx]
        start_hour = "10:00" if not is_arrival_day else "14:00"
        events.append(ItineraryEvent(
            event_id=f"d{day_number}_e{event_counter}",
            time_slot=f"{start_hour}-{int(start_hour.split(':')[0]) + int(duration)}:00",
            title=title,
            description=f"{title} in {city}",
            category=category,
            location=city,
            estimated_cost_usd=cost,
            duration_hours=duration,
        ))
        event_counter += 1

    # Lunch
    title, category, duration, cost = _LUNCH_EVENTS[day_idx % len(_LUNCH_EVENTS)]
    events.append(ItineraryEvent(
        event_id=f"d{day_number}_e{event_counter}",
        time_slot="12:30-13:30",
        title=title,
        description=f"{title} in {city}",
        category=category,
        location=city,
        estimated_cost_usd=cost,
        duration_hours=duration,
    ))
    event_counter += 1

    # Afternoon (skip if departure day or relaxed pace)
    if not is_departure_day:
        title, category, duration, cost = _AFTERNOON_EVENTS[day_idx % len(_AFTERNOON_EVENTS)]
        events.append(ItineraryEvent(
            event_id=f"d{day_number}_e{event_counter}",
            time_slot="15:00-17:00",
            title=title,
            description=f"{title} in {city}",
            category=category,
            location=city,
            estimated_cost_usd=cost,
            duration_hours=duration,
        ))
        event_counter += 1

    # Dinner (skip if departure day)
    if not is_departure_day:
        title, category, duration, cost = _DINNER_EVENTS[day_idx % len(_DINNER_EVENTS)]
        events.append(ItineraryEvent(
            event_id=f"d{day_number}_e{event_counter}",
            time_slot="19:00-20:30",
            title=title,
            description=f"{title} in {city}",
            category=category,
            location=city,
            estimated_cost_usd=cost,
            duration_hours=duration,
        ))
        event_counter += 1

    return events


def generate_mock_itinerary(
    destination: str,
    destination_cities: Optional[List[str]],
    start_date: str,
    end_date: str,
    trip_duration: int,
    budget: float,
    currency: str,
    travel_party: str,
    research_output: Optional[dict] = None,
    activity_preferences: Optional[List[str]] = None,
    pace_preference: Optional[str] = None,
    daily_rhythm: Optional[str] = None,
    arrival_time: Optional[str] = None,
    departure_time: Optional[str] = None,
) -> PlannerOutputV1:
    """
    Generate a mock day-by-day itinerary.

    Produces a contextually aware but hardcoded itinerary for
    end-to-end pipeline testing.

    Args:
        destination: Trip destination
        destination_cities: Specific cities
        start_date: Trip start date
        end_date: Trip end date
        trip_duration: Trip duration in days
        budget: Trip budget
        currency: Budget currency
        travel_party: Travel party description
        research_output: Research data (optional, from research agent)
        activity_preferences: User's activity preferences
        pace_preference: User's pace preference
        daily_rhythm: User's daily rhythm preference
        arrival_time: Arrival time on first day
        departure_time: Departure time on last day

    Returns:
        PlannerOutputV1 with populated mock itinerary
    """
    # Determine cities
    cities = destination_cities or [destination.split(",")[0].strip()]

    # Day themes
    day_themes = [
        "Arrival & Exploration",
        "Cultural Immersion",
        "Adventure Day",
        "Local Experience",
        "Nature & Relaxation",
        "Hidden Gems",
        "Departure Day",
    ]

    # Generate days
    days = []
    total_cost = 0.0
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")

    for day_num in range(1, trip_duration + 1):
        # Determine city for this day
        city_idx = min((day_num - 1) * len(cities) // trip_duration, len(cities) - 1)
        city = cities[city_idx]

        # Determine theme
        if day_num == 1:
            theme = day_themes[0]
        elif day_num == trip_duration:
            theme = day_themes[-1]
        else:
            theme = day_themes[((day_num - 1) % (len(day_themes) - 2)) + 1]

        # Generate events
        events = _generate_day_events(
            day_number=day_num,
            city=city,
            pace_preference=pace_preference,
            is_arrival_day=(day_num == 1),
            is_departure_day=(day_num == trip_duration),
        )

        day_cost = sum(e.estimated_cost_usd or 0 for e in events)
        total_cost += day_cost

        day = ItineraryDay(
            day_number=day_num,
            date=(start_dt + timedelta(days=day_num - 1)).strftime("%Y-%m-%d"),
            city=city,
            theme=theme,
            events=events,
            day_cost_estimate_usd=round(day_cost, 2),
        )
        days.append(day)

    # Cost summary
    accommodation_total = budget * 0.35
    food_total = budget * 0.20
    transport_total = budget * 0.10
    activities_total = total_cost

    total_estimated = accommodation_total + food_total + transport_total + activities_total

    cost_summary = CostSummary(
        total_estimated_usd=round(total_estimated, 2),
        budget_usd=budget,
        remaining_usd=round(budget - total_estimated, 2),
        breakdown={
            "accommodation": round(accommodation_total, 2),
            "food": round(food_total, 2),
            "transport": round(transport_total, 2),
            "activities": round(activities_total, 2),
        },
    )

    return PlannerOutputV1(
        trip_title=f"{destination} Adventure: {trip_duration}-Day Journey",
        destination=destination,
        start_date=start_date,
        end_date=end_date,
        trip_duration=trip_duration,
        days=days,
        cost_summary=cost_summary,
        planning_notes=[
            "This is a mock itinerary for pipeline testing",
            f"Budget assessment: {'tight' if budget < trip_duration * 80 else 'comfortable'}",
            "Book popular activities in advance when possible",
        ],
        metadata={
            "data_source": "mock",
            "generated_at": datetime.utcnow().isoformat(),
            "version": "v1",
        },
    )
