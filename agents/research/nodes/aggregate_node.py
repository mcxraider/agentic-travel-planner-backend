"""
Aggregate nodes for the research graph.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Tuple

from pydantic import ValidationError

from agents.shared.contracts.research_output_v2 import (
    AccommodationArea,
    Activity,
    CityResearchV2,
    CuratedHighlight,
    DiningRecommendation,
    InDestinationBudget,
    ResearchMetadata,
    ResearchOutputV2,
    SectionStatus,
    TransportOption,
    WeatherInfo,
)


logger = logging.getLogger(__name__)

StatusLiteral = Literal["ok", "missing", "critical_failure"]


def _build_research_output(
    state: Dict[str, Any],
) -> Tuple[ResearchOutputV2, List[str], List[str], Dict[str, StatusLiteral]]:
    """
    Assemble the final research output from all completed node outputs.

    Missing sections remain missing. The aggregate records per-section status
    in metadata instead of inventing placeholder content.

    Args:
        state: Current research state

    Returns:
        Tuple of (output, missing_sections, critical_failures, section_status)
    """
    missing_sections: List[str] = []
    critical_failures: List[str] = []
    section_status: Dict[str, StatusLiteral] = {}

    def _mark(section: str, present: bool, critical: bool = False) -> None:
        if present:
            section_status[section] = "ok"
            return
        missing_sections.append(section)
        if critical:
            critical_failures.append(section)
            section_status[section] = "critical_failure"
        else:
            section_status[section] = "missing"

    weather = None
    if state.get("weather_output"):
        weather = WeatherInfo.model_validate(state["weather_output"])
    _mark("weather", weather is not None)

    overview_data = state.get("destination_overview_output") or {}
    _mark("destination_overview", bool(overview_data), critical=True)

    city_name = overview_data.get("city_name")
    destination_cities = state.get("destination_cities") or []
    if not city_name and len(destination_cities) == 1:
        city_name = destination_cities[0]

    accommodation: List[AccommodationArea] = []
    if state.get("accommodation_output"):
        accommodation = [
            AccommodationArea.model_validate(item)
            for item in state["accommodation_output"].get("items", [])
        ]
    _mark("accommodation", state.get("accommodation_output") is not None)

    activities: List[Activity] = []
    if state.get("activities_output"):
        activities = [
            Activity.model_validate(item)
            for item in state["activities_output"].get("items", [])
        ]
    _mark("activities", state.get("activities_output") is not None, critical=True)

    dining: List[DiningRecommendation] = []
    if state.get("dining_output"):
        dining = [
            DiningRecommendation.model_validate(item)
            for item in state["dining_output"].get("items", [])
        ]
    _mark("dining", state.get("dining_output") is not None)

    city = CityResearchV2(
        city_name=city_name,
        country=overview_data.get("country"),
        destination_overview=overview_data.get("overview"),
        recommended_days=overview_data.get("recommended_days"),
        weather=weather,
        accommodation_areas=accommodation,
        activities=activities,
        dining=dining,
    )

    transportation: List[TransportOption] = []
    if state.get("transportation_output"):
        transportation = [
            TransportOption.model_validate(item)
            for item in state["transportation_output"].get("items", [])
        ]
    _mark("transportation", state.get("transportation_output") is not None)

    highlights: List[CuratedHighlight] = []
    if state.get("curated_highlights_output"):
        highlights = [
            CuratedHighlight.model_validate(item)
            for item in state["curated_highlights_output"].get("items", [])
        ]
    _mark("curated_highlights", state.get("curated_highlights_output") is not None)

    budget = None
    if state.get("budget_analysis_output"):
        budget = InDestinationBudget.model_validate(state["budget_analysis_output"])
    _mark("budget_analysis", budget is not None, critical=True)

    degraded = len(missing_sections) > 0
    output = ResearchOutputV2(
        destination=state["destination"],
        trip_duration_days=state["trip_duration"],
        travel_party=state["travel_party"],
        cities=[city],
        transportation=transportation,
        curated_highlights=highlights,
        budget_analysis=budget,
        metadata=ResearchMetadata(
            generated_at=datetime.now(timezone.utc).isoformat(),
            session_id=state.get("session_id"),
            degraded=degraded,
            missing_sections=missing_sections,
            critical_failures=critical_failures,
            section_status=section_status,
        ),
    )
    return output, missing_sections, critical_failures, section_status


def aggregate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assemble the normal-path research output.

    This path expects all critical sections to be present. Missing non-critical
    sections are allowed and marked in metadata.

    Args:
        state: Current research state

    Returns:
        State updates with ``research_output`` and completion status
    """
    session_id = state.get("session_id") or "unknown"
    log_prefix = f"[session={session_id}] [graph=research] [node=aggregate]"
    logger.info("%s Assembling ResearchOutputV2", log_prefix)

    try:
        output, missing, critical_failures, _ = _build_research_output(state)
        if critical_failures:
            logger.error(
                "%s Critical sections unexpectedly missing on normal path: %s",
                log_prefix,
                critical_failures,
            )
            return {
                "research_output": None,
                "research_complete": False,
                "errors": [
                    f"aggregate: critical sections missing on normal path: {critical_failures}"
                ],
                "messages": [
                    {
                        "role": "system",
                        "agent": "research",
                        "content": f"aggregate failed: critical sections missing {critical_failures}",
                    }
                ],
            }

        if missing:
            logger.warning("%s Non-critical sections missing: %s", log_prefix, missing)

        return {
            "research_output": output.model_dump(),
            "research_complete": True,
            "errors": [f"missing non-critical sections: {missing}"] if missing else [],
            "messages": [
                {
                    "role": "system",
                    "agent": "research",
                    "content": "aggregate complete",
                }
            ],
        }
    except ValidationError as exc:
        logger.error("%s Validation failed: %s", log_prefix, exc)
        return {
            "research_output": None,
            "research_complete": False,
            "errors": [f"aggregate: schema validation failed: {exc}"],
            "messages": [
                {
                    "role": "system",
                    "agent": "research",
                    "content": f"aggregate schema validation failed: {exc}",
                }
            ],
        }


def degraded_aggregate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assemble a degraded research output after critical repair failure.

    Args:
        state: Current research state

    Returns:
        State updates with a degraded ``research_output`` if assembly succeeds
    """
    session_id = state.get("session_id") or "unknown"
    log_prefix = f"[session={session_id}] [graph=research] [node=degraded_aggregate]"
    logger.warning("%s Entering degraded mode due to critical node failure", log_prefix)

    try:
        output, missing, critical_failures, _ = _build_research_output(state)
        logger.warning(
            "%s Degraded output assembled. Missing: %s. Critical failures: %s",
            log_prefix,
            missing,
            critical_failures,
        )
        return {
            "research_output": output.model_dump(),
            "research_complete": True,
            "errors": [f"degraded: critical sections missing: {critical_failures}"],
            "messages": [
                {
                    "role": "system",
                    "agent": "research",
                    "content": f"degraded aggregate complete: {critical_failures}",
                }
            ],
        }
    except ValidationError as exc:
        logger.error("%s Even degraded assembly failed: %s", log_prefix, exc)
        return {
            "research_output": None,
            "research_complete": False,
            "errors": [f"degraded_aggregate: schema validation failed: {exc}"],
            "messages": [
                {
                    "role": "system",
                    "agent": "research",
                    "content": f"degraded aggregate schema validation failed: {exc}",
                }
            ],
        }


__all__ = [
    "aggregate_node",
    "degraded_aggregate_node",
]
