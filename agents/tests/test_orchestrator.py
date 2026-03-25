"""
Tests for the multi-agent orchestrator pipeline.

Tests the orchestrator graph, research/planner standalone graphs,
and contract validation at each stage.
"""

from datetime import datetime, timezone

import pytest

import agents.graph.build as orchestrator_build
from agents.graph.build import create_orchestrator_graph
from agents.graph.router import route_next_agent
from agents.research.graph.build import create_research_graph
from agents.research.nodes.research import research_node
from agents.research.mock_data import generate_mock_research
from agents.planner.graph.build import create_planner_graph
from agents.planner.nodes.planner import planner_node
from agents.planner.mock_data import generate_mock_itinerary
from agents.shared.contracts.research_output import ResearchOutputV1
from agents.shared.contracts.research_output_v2 import ResearchOutputV2
from agents.shared.contracts.planner_output import PlannerOutputV1


# ============================================================================
# Test Fixtures
# ============================================================================


def _make_trip_context():
    """Create a minimal trip context for testing."""
    return {
        "destination": "Bali, Indonesia",
        "destination_cities": ["Ubud", "Seminyak"],
        "start_date": "2025-06-01",
        "end_date": "2025-06-04",
        "trip_duration": 4,
        "budget": 1500.0,
        "currency": "USD",
        "travel_party": "2 adults",
        "budget_scope": "Total trip budget",
    }


def _make_clarification_output():
    """Create a mock ClarificationOutput dict for testing."""
    return {
        "activity_preferences": ["nature/hiking", "food/gastronomy"],
        "pace_preference": "moderate",
        "tourist_vs_local": "balanced",
        "mobility_level": "high",
        "dining_style": ["street food", "casual"],
        "top_3_must_dos": {
            "1": "Rice terrace trek",
            "2": "Temple visit",
            "3": "Beach day",
        },
        "transportation_mode": ["scooter rental", "walking"],
        "arrival_time": "Early AM (<9am)",
        "departure_time": "Afternoon (12-5pm)",
        "budget_priority": "experiences > comfort",
        "accommodation_style": ["mid-range hotel"],
        "daily_rhythm": "early bird",
        "downtime_preference": "some rest",
        "completeness_score": 89,
        "rounds_completed": 3,
    }


def _make_orchestrator_initial_state():
    """Create initial orchestrator state for testing."""
    ctx = _make_trip_context()
    return {
        **ctx,
        "clarification_output": _make_clarification_output(),
        "research_output": None,
        "planner_output": None,
        "current_agent": "starting",
        "errors": [],
        "messages": [
            {
                "role": "system",
                "agent": "orchestrator",
                "content": "Pipeline started for testing",
            }
        ],
        "session_id": "test-session-001",
    }


def _make_mock_research_output_v2():
    """Create a deterministic ResearchOutputV2 fixture for orchestrator tests."""
    return {
        "destination": "Bali, Indonesia",
        "trip_duration_days": 4,
        "travel_party": "2 adults",
        "cities": [
            {
                "city_name": "Ubud",
                "country": "Indonesia",
                "destination_overview": "Cultural heart of Bali with temples and rice terraces.",
                "recommended_days": 2,
                "weather": {
                    "season": "dry season",
                    "temperature_range_celsius": {"min": 24.0, "max": 31.0},
                    "precipitation_likelihood": "moderate",
                    "daylight_hours": 12.3,
                    "clothing_recommendations": ["lightweight clothing", "rain layer"],
                    "weather_notes": ["Afternoon showers are possible."],
                },
                "accommodation_areas": [
                    {
                        "neighborhood": "Ubud Center",
                        "description": "Walkable base near markets and cafes.",
                        "why_suitable": "Balances convenience and mid-range pricing.",
                        "price_tier": "mid-range",
                        "pros": ["central", "easy dining access"],
                        "cons": ["busy traffic"],
                    }
                ],
                "activities": [
                    {
                        "name": "Tegallalang Rice Terrace",
                        "category": "nature",
                        "neighborhood": "Tegallalang",
                        "description": "Scenic rice terrace walk near Ubud.",
                        "estimated_duration_hours": 2.0,
                        "estimated_cost_usd": 5.0,
                        "travel_time_from_centre_mins": 20,
                        "best_time_to_visit": "early morning",
                        "booking_required": False,
                        "tags": ["nature", "photography"],
                    }
                ],
                "dining": [
                    {
                        "name": "Hujan Locale",
                        "cuisine_type": "Indonesian",
                        "description": "Polished local dishes in central Ubud.",
                        "price_tier": "mid-range",
                        "estimated_cost_per_person_usd": 18.0,
                        "must_try_dishes": ["bebek betutu"],
                        "neighborhood": "Ubud Center",
                        "best_for": "dinner",
                    }
                ],
            }
        ],
        "transportation": [
            {
                "mode": "private driver",
                "description": "Best for inter-area transfers and day trips.",
                "estimated_daily_cost_usd": 35.0,
                "coverage": "Across south and central Bali",
                "tips": ["Book the day before"],
            }
        ],
        "curated_highlights": [
            {
                "rank": 1,
                "category": "experience",
                "title": "Sunrise rice terrace walk",
                "why_it_matters": "Matches the traveler's nature and culture preferences.",
                "estimated_duration_hours": 2.0,
                "estimated_cost_usd": 5.0,
            }
        ],
        "budget_analysis": {
            "total_available_usd": 1500.0,
            "trip_duration_days": 4,
            "daily_budget_usd": 375.0,
            "breakdown": {
                "accommodation": 525.0,
                "food": 250.0,
                "activities": 300.0,
                "transport": 150.0,
            },
            "budget_assessment": "comfortable",
            "budget_tips": ["Use a private driver for multi-stop days."],
        },
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "session_id": "test-session-001",
            "degraded": False,
            "missing_sections": [],
            "critical_failures": [],
            "section_status": {
                "weather": "ok",
                "destination_overview": "ok",
                "budget_analysis": "ok",
                "accommodation": "ok",
                "activities": "ok",
                "dining": "ok",
                "transportation": "ok",
                "curated_highlights": "ok",
            },
        },
    }


class _StubResearchGraph:
    """Simple stand-in for the staged research graph in orchestrator tests."""

    def invoke(self, state, config=None):
        return {
            **state,
            "research_output": _make_mock_research_output_v2(),
            "research_complete": True,
            "errors": [],
            "messages": [
                {
                    "role": "system",
                    "agent": "research",
                    "content": "Research complete for Bali, Indonesia.",
                }
            ],
        }


# ============================================================================
# TestOrchestratorPipeline
# ============================================================================


class TestOrchestratorPipeline:
    """Tests for the full orchestrator pipeline."""

    @pytest.fixture(autouse=True)
    def _mock_research_graph(self, monkeypatch):
        """Keep orchestrator tests offline by stubbing the research sub-graph."""
        monkeypatch.setattr(
            orchestrator_build,
            "create_research_graph",
            lambda: _StubResearchGraph(),
        )

    def test_pipeline_completes(self):
        """Pipeline should run to completion with all outputs populated."""
        graph = create_orchestrator_graph()
        initial_state = _make_orchestrator_initial_state()

        result = graph.invoke(initial_state)

        assert result["current_agent"] == "complete"
        assert result["research_output"] is not None
        assert result["planner_output"] is not None
        assert len(result.get("errors", [])) == 0

    def test_research_output_populated(self):
        """Research output should contain expected structure."""
        graph = create_orchestrator_graph()
        initial_state = _make_orchestrator_initial_state()

        result = graph.invoke(initial_state)

        research = result["research_output"]
        assert research["destination"] == "Bali, Indonesia"
        assert len(research["cities"]) > 0
        assert "transportation" in research
        assert "budget_analysis" in research

    def test_planner_output_populated(self):
        """Planner output should contain expected structure."""
        graph = create_orchestrator_graph()
        initial_state = _make_orchestrator_initial_state()

        result = graph.invoke(initial_state)

        planner = result["planner_output"]
        assert planner["destination"] == "Bali, Indonesia"
        assert planner["trip_duration"] == 4
        assert len(planner["days"]) == 4
        assert "cost_summary" in planner

    def test_messages_tracking(self):
        """Messages should track pipeline progress."""
        graph = create_orchestrator_graph()
        initial_state = _make_orchestrator_initial_state()

        result = graph.invoke(initial_state)

        messages = result["messages"]
        # Should have: initial + research + planner + completion
        assert len(messages) >= 4

        # Check agents are represented
        agents_seen = {m.get("agent") for m in messages}
        assert "orchestrator" in agents_seen
        assert "research" in agents_seen
        assert "planner" in agents_seen

    def test_clarification_passthrough(self):
        """Clarification output should be preserved in final state."""
        graph = create_orchestrator_graph()
        initial_state = _make_orchestrator_initial_state()

        result = graph.invoke(initial_state)

        assert result["clarification_output"] is not None
        assert result["clarification_output"]["pace_preference"] == "moderate"

    def test_pipeline_without_clarification_output(self):
        """Pipeline should work even without clarification output."""
        graph = create_orchestrator_graph()
        initial_state = _make_orchestrator_initial_state()
        initial_state["clarification_output"] = None

        result = graph.invoke(initial_state)

        assert result["current_agent"] == "complete"
        assert result["research_output"] is not None
        assert result["planner_output"] is not None

    def test_pipeline_skips_research_if_already_done(self):
        """Pipeline should skip research if research_output is pre-populated."""
        graph = create_orchestrator_graph()
        initial_state = _make_orchestrator_initial_state()

        # Pre-populate research output
        initial_state["research_output"] = _make_mock_research_output_v2()

        result = graph.invoke(initial_state)

        assert result["current_agent"] == "complete"
        assert result["planner_output"] is not None
        # Research should not have been re-run (no research message added)
        research_messages = [
            m for m in result["messages"] if m.get("agent") == "research"
        ]
        assert len(research_messages) == 0


# ============================================================================
# TestContracts
# ============================================================================


class TestContracts:
    """Tests for contract validation at each stage."""

    @pytest.fixture(autouse=True)
    def _mock_research_graph(self, monkeypatch):
        """Keep orchestrator contract tests offline by stubbing research."""
        monkeypatch.setattr(
            orchestrator_build,
            "create_research_graph",
            lambda: _StubResearchGraph(),
        )

    def test_research_output_validates_against_contract(self):
        """Research output should validate against ResearchOutputV2."""
        graph = create_orchestrator_graph()
        initial_state = _make_orchestrator_initial_state()

        result = graph.invoke(initial_state)

        # Should not raise
        validated = ResearchOutputV2.model_validate(result["research_output"])
        assert validated.destination == "Bali, Indonesia"
        assert len(validated.cities) > 0

    def test_planner_output_validates_against_contract(self):
        """Planner output should validate against PlannerOutputV1."""
        graph = create_orchestrator_graph()
        initial_state = _make_orchestrator_initial_state()

        result = graph.invoke(initial_state)

        # Should not raise
        validated = PlannerOutputV1.model_validate(result["planner_output"])
        assert validated.destination == "Bali, Indonesia"
        assert len(validated.days) == 4

    def test_research_mock_data_matches_contract(self):
        """generate_mock_research output should match ResearchOutputV1."""
        output = generate_mock_research(
            destination="Tokyo, Japan",
            destination_cities=["Tokyo", "Kyoto"],
            trip_duration=5,
            budget=2000.0,
            currency="USD",
            travel_party="1 adult",
        )

        # Should already be the right type
        assert isinstance(output, ResearchOutputV1)

        # Round-trip through dict should also validate
        validated = ResearchOutputV1.model_validate(output.model_dump())
        assert validated.destination == "Tokyo, Japan"
        assert len(validated.cities) == 2

    def test_planner_mock_data_matches_contract(self):
        """generate_mock_itinerary output should match PlannerOutputV1."""
        output = generate_mock_itinerary(
            destination="Tokyo, Japan",
            destination_cities=["Tokyo", "Kyoto"],
            start_date="2025-07-01",
            end_date="2025-07-05",
            trip_duration=5,
            budget=2000.0,
            currency="USD",
            travel_party="1 adult",
        )

        # Should already be the right type
        assert isinstance(output, PlannerOutputV1)

        # Round-trip through dict should also validate
        validated = PlannerOutputV1.model_validate(output.model_dump())
        assert validated.destination == "Tokyo, Japan"
        assert len(validated.days) == 5


# ============================================================================
# TestResearchStandalone
# ============================================================================


class TestResearchStandalone:
    """Tests for the research agent running independently."""

    def test_research_graph_runs(self):
        """Research graph should compile successfully."""
        graph = create_research_graph()

        assert graph is not None
        assert type(graph).__name__ == "CompiledStateGraph"

    def test_research_node_directly(self):
        """Research node function should work when called directly."""
        state = {
            "destination": "Paris, France",
            "destination_cities": ["Paris"],
            "start_date": "2025-08-01",
            "end_date": "2025-08-03",
            "trip_duration": 3,
            "budget": 1000.0,
            "currency": "EUR",
            "travel_party": "1 adult",
            "activity_preferences": None,
            "accommodation_style": None,
            "research_output": None,
            "research_complete": False,
            "messages": [],
            "session_id": None,
        }

        result = research_node(state)

        assert result["research_complete"] is True
        assert result["research_output"] is not None
        assert result["research_output"]["destination"] == "Paris, France"


# ============================================================================
# TestPlannerStandalone
# ============================================================================


class TestPlannerStandalone:
    """Tests for the planner agent running independently."""

    def test_planner_graph_runs(self):
        """Planner graph should execute and produce output."""
        graph = create_planner_graph()
        ctx = _make_trip_context()

        initial_state = {
            "destination": ctx["destination"],
            "destination_cities": ctx["destination_cities"],
            "start_date": ctx["start_date"],
            "end_date": ctx["end_date"],
            "trip_duration": ctx["trip_duration"],
            "budget": ctx["budget"],
            "currency": ctx["currency"],
            "travel_party": ctx["travel_party"],
            "activity_preferences": ["nature/hiking"],
            "pace_preference": "moderate",
            "dining_style": ["casual"],
            "daily_rhythm": "early bird",
            "arrival_time": "Early AM",
            "departure_time": "Afternoon",
            "research_output": None,
            "planner_output": None,
            "planner_complete": False,
            "messages": [],
            "session_id": "test-planner-001",
        }

        result = graph.invoke(initial_state)

        assert result["planner_complete"] is True
        assert result["planner_output"] is not None
        assert len(result["messages"]) > 0

    def test_planner_node_directly(self):
        """Planner node function should work when called directly."""
        state = {
            "destination": "Paris, France",
            "destination_cities": ["Paris"],
            "start_date": "2025-08-01",
            "end_date": "2025-08-03",
            "trip_duration": 3,
            "budget": 1000.0,
            "currency": "EUR",
            "travel_party": "1 adult",
            "activity_preferences": None,
            "pace_preference": None,
            "dining_style": None,
            "daily_rhythm": None,
            "arrival_time": None,
            "departure_time": None,
            "research_output": None,
            "planner_output": None,
            "planner_complete": False,
            "messages": [],
            "session_id": None,
        }

        result = planner_node(state)

        assert result["planner_complete"] is True
        assert result["planner_output"] is not None
        assert result["planner_output"]["destination"] == "Paris, France"
        assert len(result["planner_output"]["days"]) == 3

    def test_planner_generates_correct_day_count(self):
        """Planner should generate the correct number of days."""
        for duration in [1, 3, 7]:
            output = generate_mock_itinerary(
                destination="Test",
                destination_cities=["City"],
                start_date="2025-01-01",
                end_date=f"2025-01-{duration:02d}",
                trip_duration=duration,
                budget=500.0 * duration,
                currency="USD",
                travel_party="1 adult",
            )
            assert len(output.days) == duration


# ============================================================================
# TestRouter
# ============================================================================


class TestRouter:
    """Tests for the orchestrator routing logic."""

    def test_routes_to_research_when_missing(self):
        """Should route to research when research_output is None."""
        state = {"research_output": None, "planner_output": None}
        assert route_next_agent(state) == "research_node"

    def test_routes_to_planner_when_research_done(self):
        """Should route to planner when research is done but planner is not."""
        state = {"research_output": {"some": "data"}, "planner_output": None}
        assert route_next_agent(state) == "planner_node"

    def test_routes_to_complete_when_all_done(self):
        """Should route to complete when both outputs are populated."""
        state = {
            "research_output": {"some": "data"},
            "planner_output": {"some": "data"},
        }
        assert route_next_agent(state) == "complete"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
