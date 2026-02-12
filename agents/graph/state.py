"""
Orchestrator state schema.

Defines the top-level state that flows through the orchestrator graph,
carrying trip context and handoff data between agents.
"""

from typing import TypedDict, List, Optional, Annotated
import operator


class OrchestratorState(TypedDict):
    """
    State schema for the orchestrator graph.

    Carries trip context plus handoff slots for each agent's output.
    The orchestrator does NOT embed clarification as a sub-graph
    (due to human-in-the-loop). Instead, it takes completed
    clarification output as input.
    """

    # Trip context (from clarification session)
    destination: str
    destination_cities: Optional[List[str]]
    start_date: str
    end_date: str
    trip_duration: int
    budget: float
    currency: str
    travel_party: str
    budget_scope: str

    # Clarification preferences (from ClarificationOutputV2)
    clarification_output: Optional[dict]

    # Agent handoff slots (populated as agents complete)
    research_output: Optional[dict]
    planner_output: Optional[dict]

    # Orchestrator tracking
    current_agent: str
    errors: Annotated[List[str], operator.add]
    messages: Annotated[List[dict], operator.add]

    # Session tracking
    session_id: Optional[str]
