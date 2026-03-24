"""
Integration tests for the staged research pipeline.

These tests exercise the compiled research graph with real LLM calls.
They are opt-in because they require network access, OpenAI credentials,
and incur model usage cost.
"""

import os

import pytest
from langgraph.checkpoint.memory import MemorySaver

from agents.research.graph.build import create_research_graph
from agents.shared.contracts.research_output_v2 import ResearchOutputV2


LIVE_RESEARCH_TESTS_ENABLED = os.environ.get("RUN_LIVE_LLM_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not LIVE_RESEARCH_TESTS_ENABLED,
    reason="Set RUN_LIVE_LLM_TESTS=1 to run live research pipeline tests.",
)


SYNTHETIC_STATE = {
    "destination": "Tokyo",
    "destination_cities": ["Tokyo"],
    "start_date": "2026-04-10",
    "end_date": "2026-04-17",
    "trip_duration": 7,
    "budget": 2000.0,
    "currency": "USD",
    "travel_party": "couple",
    "activity_preferences": ["temples", "food tours", "street markets"],
    "pace_preference": "moderate",
    "tourist_vs_local": "mix",
    "mobility_level": "full",
    "dining_style": ["local street food", "sit-down restaurants"],
    "top_3_must_dos": {
        "1": "Tsukiji fish market",
        "2": "TeamLab",
        "3": "Shibuya crossing",
    },
    "budget_priority": "experiences_over_comfort",
    "accommodation_style": ["boutique hotel", "central location"],
    "dietary_restrictions": None,
    "clarification_output": None,
    "weather_output": None,
    "destination_overview_output": None,
    "budget_analysis_output": None,
    "accommodation_output": None,
    "activities_output": None,
    "dining_output": None,
    "transportation_output": None,
    "curated_highlights_output": None,
    "repair_target": None,
    "repair_attempt_count": 0,
    "last_bad_response": None,
    "last_repaired_node": None,
    "research_output": None,
    "research_complete": False,
    "errors": [],
    "messages": [],
    "session_id": "test-001",
}


def test_research_pipeline_end_to_end():
    """Full staged research pipeline run with real LLM calls."""
    checkpointer = MemorySaver()
    graph = create_research_graph(checkpointer=checkpointer)
    invoke_config = {"configurable": {"thread_id": "research-test-001"}}

    result = graph.invoke(SYNTHETIC_STATE, config=invoke_config)

    assert result["research_complete"] is True
    assert result["research_output"] is not None

    output = ResearchOutputV2(**result["research_output"])
    assert output.destination == "Tokyo"
    assert len(output.cities) >= 1
    assert len(output.cities[0].activities) >= 5
    assert len(output.curated_highlights) >= 3
    assert output.budget_analysis is not None
    assert output.budget_analysis.total_available_usd == 2000.0
    assert output.budget_analysis.trip_duration_days == 7

    names = [activity.name for activity in output.cities[0].activities]
    assert any(
        keyword in name
        for name in names
        for keyword in ("Senso", "Shibuya", "Tsukiji", "TeamLab", "Shinjuku")
    )


def test_research_pipeline_checkpoint_resume():
    """Verify the checkpointer stores final state on a stable thread id."""
    checkpointer = MemorySaver()
    graph = create_research_graph(checkpointer=checkpointer)
    invoke_config = {"configurable": {"thread_id": "research-resume-001"}}

    result = graph.invoke(SYNTHETIC_STATE, config=invoke_config)

    assert result["research_complete"] is True

    state_snapshot = graph.get_state(invoke_config)
    assert state_snapshot.values["research_complete"] is True
