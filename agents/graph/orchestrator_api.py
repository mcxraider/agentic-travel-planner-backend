"""
FastAPI endpoints for the orchestrator.

Provides the API to run the full research -> planner pipeline
given trip context and clarification output.
"""

import logging
import uuid
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.graph.build import create_orchestrator_graph


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])


# ============================================================================
# Request/Response Models
# ============================================================================


class OrchestratorRunRequest(BaseModel):
    """Request to run the orchestrator pipeline."""

    # Trip context
    destination: str = Field(description="Trip destination")
    destination_cities: Optional[List[str]] = Field(
        default=None, description="Specific cities to visit"
    )
    start_date: str = Field(description="Trip start date (YYYY-MM-DD)")
    end_date: str = Field(description="Trip end date (YYYY-MM-DD)")
    trip_duration: int = Field(ge=1, description="Trip duration in days")
    budget: float = Field(gt=0, description="Trip budget")
    currency: str = Field(default="USD", description="Budget currency")
    travel_party: str = Field(default="1 adult", description="Who is traveling")
    budget_scope: str = Field(
        default="Total trip budget", description="What budget covers"
    )

    # Clarification output (from completed clarification session)
    clarification_output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Completed ClarificationOutputV2 data",
    )


class OrchestratorRunResponse(BaseModel):
    """Response from the orchestrator pipeline."""

    session_id: str = Field(description="Pipeline session identifier")
    status: str = Field(description="Pipeline status: 'complete' or 'error'")
    research_output: Optional[Dict[str, Any]] = Field(
        default=None, description="Research agent output"
    )
    planner_output: Optional[Dict[str, Any]] = Field(
        default=None, description="Planner agent output"
    )
    messages: List[Dict[str, Any]] = Field(
        default_factory=list, description="Pipeline tracking messages"
    )
    errors: List[str] = Field(
        default_factory=list, description="Any errors encountered"
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/run", response_model=OrchestratorRunResponse)
async def run_orchestrator(request: OrchestratorRunRequest):
    """
    Run the full orchestrator pipeline.

    Takes trip context and clarification output, runs research and planner
    agents sequentially, and returns both outputs.
    """
    session_id = str(uuid.uuid4())
    _log = f"[session={session_id}] [graph=orchestrator] [api=run] "

    logger.info(
        f"{_log}Pipeline starting | destination={request.destination}, "
        f"duration={request.trip_duration}d, budget={request.budget} {request.currency}, "
        f"has_clarification={request.clarification_output is not None}"
    )

    try:
        # Create the orchestrator graph
        graph = create_orchestrator_graph()

        # Build initial state
        initial_state = {
            "destination": request.destination,
            "destination_cities": request.destination_cities,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "trip_duration": request.trip_duration,
            "budget": request.budget,
            "currency": request.currency,
            "travel_party": request.travel_party,
            "budget_scope": request.budget_scope,
            "clarification_output": request.clarification_output,
            "research_output": None,
            "planner_output": None,
            "current_agent": "starting",
            "errors": [],
            "messages": [
                {
                    "role": "system",
                    "agent": "orchestrator",
                    "content": f"Pipeline started for {request.destination}",
                }
            ],
            "session_id": session_id,
        }

        # Run the graph
        logger.info(f"{_log}Invoking orchestrator graph | entry=route_next_agent")
        final_state = graph.invoke(initial_state)

        # Determine status
        has_errors = len(final_state.get("errors", [])) > 0
        status = "error" if has_errors else "complete"

        logger.info(
            f"{_log}Pipeline finished | status={status}, "
            f"research={'done' if final_state.get('research_output') else 'missing'}, "
            f"planner={'done' if final_state.get('planner_output') else 'missing'}, "
            f"errors={len(final_state.get('errors', []))}, "
            f"messages={len(final_state.get('messages', []))}"
        )

        return OrchestratorRunResponse(
            session_id=session_id,
            status=status,
            research_output=final_state.get("research_output"),
            planner_output=final_state.get("planner_output"),
            messages=final_state.get("messages", []),
            errors=final_state.get("errors", []),
        )

    except Exception as e:
        logger.exception(f"{_log}Pipeline failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline execution failed: {str(e)}",
        )
