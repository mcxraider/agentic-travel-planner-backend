"""
Routing functions for the research graph.
"""

import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)

# Ordered pipeline sequence used for forward routing.
NODE_SEQUENCE = [
    "weather",
    "overview",
    "budget",
    "accommodation",
    "activities",
    "dining",
    "transport",
    "highlights",
    "aggregate",
]

# Critical nodes do not silently skip forward when repair fails.
CRITICAL_NODES = {"overview", "budget", "activities"}

OUTPUT_KEYS = {
    "weather": "weather_output",
    "overview": "destination_overview_output",
    "budget": "budget_analysis_output",
    "accommodation": "accommodation_output",
    "activities": "activities_output",
    "dining": "dining_output",
    "transport": "transportation_output",
    "highlights": "curated_highlights_output",
}


def _next_node(current: str) -> str:
    """
    Get the next node in the linear pipeline.

    Args:
        current: Current node name

    Returns:
        Next node name, or ``aggregate`` as a safe fallback.
    """
    if current not in NODE_SEQUENCE:
        return "aggregate"
    idx = NODE_SEQUENCE.index(current)
    return NODE_SEQUENCE[idx + 1] if idx + 1 < len(NODE_SEQUENCE) else "aggregate"


def route_after_weather(state: Dict[str, Any]) -> str:
    """Route after the weather node."""
    next_node = "repair" if state.get("repair_target") == "weather" else "overview"
    logger.info(
        "[session=%s] [graph=research] [route=weather] -> %s",
        state.get("session_id") or "unknown",
        next_node,
    )
    return next_node


def route_after_overview(state: Dict[str, Any]) -> str:
    """Route after the overview node."""
    next_node = "repair" if state.get("repair_target") == "overview" else "budget"
    logger.info(
        "[session=%s] [graph=research] [route=overview] -> %s",
        state.get("session_id") or "unknown",
        next_node,
    )
    return next_node


def route_after_budget(state: Dict[str, Any]) -> str:
    """Route after the budget node."""
    next_node = "repair" if state.get("repair_target") == "budget" else "accommodation"
    logger.info(
        "[session=%s] [graph=research] [route=budget] -> %s",
        state.get("session_id") or "unknown",
        next_node,
    )
    return next_node


def route_after_accommodation(state: Dict[str, Any]) -> str:
    """Route after the accommodation node."""
    next_node = (
        "repair" if state.get("repair_target") == "accommodation" else "activities"
    )
    logger.info(
        "[session=%s] [graph=research] [route=accommodation] -> %s",
        state.get("session_id") or "unknown",
        next_node,
    )
    return next_node


def route_after_activities(state: Dict[str, Any]) -> str:
    """Route after the activities node."""
    next_node = "repair" if state.get("repair_target") == "activities" else "dining"
    logger.info(
        "[session=%s] [graph=research] [route=activities] -> %s",
        state.get("session_id") or "unknown",
        next_node,
    )
    return next_node


def route_after_dining(state: Dict[str, Any]) -> str:
    """Route after the dining node."""
    next_node = "repair" if state.get("repair_target") == "dining" else "transport"
    logger.info(
        "[session=%s] [graph=research] [route=dining] -> %s",
        state.get("session_id") or "unknown",
        next_node,
    )
    return next_node


def route_after_transport(state: Dict[str, Any]) -> str:
    """Route after the transport node."""
    next_node = "repair" if state.get("repair_target") == "transport" else "highlights"
    logger.info(
        "[session=%s] [graph=research] [route=transport] -> %s",
        state.get("session_id") or "unknown",
        next_node,
    )
    return next_node


def route_after_highlights(state: Dict[str, Any]) -> str:
    """Route after the highlights node."""
    next_node = "repair" if state.get("repair_target") == "highlights" else "aggregate"
    logger.info(
        "[session=%s] [graph=research] [route=highlights] -> %s",
        state.get("session_id") or "unknown",
        next_node,
    )
    return next_node


def route_after_repair(state: Dict[str, Any]) -> str:
    """
    Route after the repair node.

    Successful repair continues forward. Failed repair skips forward for
    non-critical nodes, and branches to degraded aggregation for critical nodes.

    Args:
        state: Current research state

    Returns:
        Next node name
    """
    last = state.get("last_repaired_node") or ""
    if not last:
        logger.info(
            "[session=%s] [graph=research] [route=repair] no repaired node recorded -> aggregate",
            state.get("session_id") or "unknown",
        )
        return "aggregate"

    output_key = OUTPUT_KEYS.get(last)
    repair_succeeded = state.get(output_key) is not None if output_key else False
    if not repair_succeeded and last in CRITICAL_NODES:
        logger.info(
            "[session=%s] [graph=research] [route=repair] target=%s failed critical repair -> degraded_aggregate",
            state.get("session_id") or "unknown",
            last,
        )
        return "degraded_aggregate"

    next_node = _next_node(last)
    logger.info(
        "[session=%s] [graph=research] [route=repair] target=%s succeeded=%s -> %s",
        state.get("session_id") or "unknown",
        last,
        repair_succeeded,
        next_node,
    )
    return next_node


__all__ = [
    "CRITICAL_NODES",
    "NODE_SEQUENCE",
    "OUTPUT_KEYS",
    "route_after_weather",
    "route_after_overview",
    "route_after_budget",
    "route_after_accommodation",
    "route_after_activities",
    "route_after_dining",
    "route_after_transport",
    "route_after_highlights",
    "route_after_repair",
]
