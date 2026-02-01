"""
FastAPI endpoints for the clarification agent.

Provides REST API for starting clarification sessions, submitting
responses, and managing session state.
"""

import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status

from agents.clarification.schemas import (
    ClarificationState,
    StartSessionRequest,
    StartSessionResponse,
    RespondRequest,
    RespondResponse,
    SessionStatusResponse,
    Question,
    QuestionsState,
    # V2 models
    StartSessionResponseV2,
    RespondResponseV2,
    QuestionV2,
    QuestionsStateV2,
    ClarificationDataV2,
)
from agents.clarification.graph.build import create_clarification_graph
from agents.clarification.response_parser import merge_collected_data
from agents.clarification.prompts.builders import (
    get_initial_data_object,
    merge_user_responses_into_data,
)
from agents.shared.logging.debug_logger import get_or_create_logger, remove_logger


# Create router for clarification route
router = APIRouter(prefix="/api/clarification", tags=["clarification"])

# In-memory session storage (replace with Redis/DB in production)
_sessions: Dict[str, Dict[str, Any]] = {}

# Compiled graph instance (shared across requests)
_graph = None


def get_graph():
    """Get or create the shared graph instance."""
    global _graph
    if _graph is None:
        _graph = create_clarification_graph()
    return _graph


def create_initial_state(request: StartSessionRequest, session_id: str) -> ClarificationState:
    """Create initial state from a start session request."""
    start = datetime.strptime(request.start_date, "%Y-%m-%d")
    end = datetime.strptime(request.end_date, "%Y-%m-%d")
    duration = (end - start).days + 1

    return {
        # User context
        "user_name": request.user_name,
        "citizenship": request.citizenship,
        "health_limitations": request.health_limitations,
        "work_obligations": request.work_obligations,
        "dietary_restrictions": request.dietary_restrictions,
        "specific_interests": request.specific_interests,
        # Trip basics
        "destination": request.destination,
        "destination_cities": request.destination_cities,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "trip_duration": duration,
        "budget": request.budget,
        "currency": request.currency,
        "travel_party": request.travel_party,
        "budget_scope": request.budget_scope,
        # Process state
        "current_round": 1,
        "completeness_score": 0,
        "clarification_complete": False,
        # Data collection
        "current_questions": None,
        "user_response": None,
        "collected_data": {},
        # V2: Initialize data object with all fields as null
        "data": get_initial_data_object(),
        "messages": [],
        # Debug/tracking
        "session_id": session_id,
    }


@router.post("/start", response_model=StartSessionResponseV2)
async def start_session(request: StartSessionRequest) -> StartSessionResponseV2:
    """
    Start a new clarification session (v2).

    Creates a new session with the provided user and trip information,
    then runs the first clarification round to generate initial questions.

    Args:
        request: Session start request with user/trip details

    Returns:
        Session ID, first round of questions, state, and data object
    """
    # Start API timing
    api_start_time = time.perf_counter()

    # Generate session ID
    session_id = str(uuid.uuid4())

    # Get or create debug logger from registry (ensures same instance is used)
    debug_logger = get_or_create_logger(session_id)

    # Create initial state with session_id
    initial_state = create_initial_state(request, session_id)

    # Get graph and run first round
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}

    try:
        # calls the graph, for the current state
        result = graph.invoke(initial_state, config)

        if result is None:
            api_duration_ms = (time.perf_counter() - api_start_time) * 1000
            debug_logger.log_api_timing(
                endpoint="/api/clarification/start",
                duration_ms=api_duration_ms,
                round_num=1,
                success=False,
                error="Graph execution failed - no result returned",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Graph execution failed - no result returned",
            )

        # Store session state
        _sessions[session_id] = {
            "state": result,
            "config": config,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Extract questions from result (v2 format)
        questions_data = result.get("current_questions", {})

        if not questions_data:
            api_duration_ms = (time.perf_counter() - api_start_time) * 1000
            debug_logger.log_api_timing(
                endpoint="/api/clarification/start",
                duration_ms=api_duration_ms,
                round_num=1,
                success=False,
                error="No questions generated in first round",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No questions generated in first round",
            )

        # Build v2 response
        questions = [
            QuestionV2(
                id=q["id"],
                field=q["field"],
                tier=q.get("tier", 1),
                question=q["question"],
                type=q.get("type", "single_select"),
                options=q.get("options", []),
                min_selections=q.get("min_selections"),
                max_selections=q.get("max_selections"),
                allow_custom=q.get("allow_custom", False),
            )
            for q in questions_data.get("questions", [])
        ]

        state_info = questions_data.get("state", {})
        data_info = questions_data.get("data", {})

        # Log successful API timing
        api_duration_ms = (time.perf_counter() - api_start_time) * 1000
        debug_logger.log_api_timing(
            endpoint="/api/clarification/start",
            duration_ms=api_duration_ms,
            round_num=1,
            success=True,
        )

        print(result)
        return StartSessionResponseV2(
            session_id=session_id,
            round=questions_data.get("round", 1),
            questions=questions,
            state=QuestionsStateV2(
                collected=state_info.get("collected", []),
                missing_tier1=state_info.get("missing_tier1", []),
                missing_tier2=state_info.get("missing_tier2", []),
                conflicts_detected=state_info.get("conflicts_detected", []),
                score=state_info.get("score", 0),
            ),
            data=ClarificationDataV2(**data_info) if data_info else ClarificationDataV2(),
        )

    except HTTPException:
        raise
    except Exception as e:
        api_duration_ms = (time.perf_counter() - api_start_time) * 1000
        debug_logger.log_api_timing(
            endpoint="/api/clarification/start",
            duration_ms=api_duration_ms,
            round_num=1,
            success=False,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start session: {str(e)}",
        )


@router.post("/respond", response_model=RespondResponseV2)
async def respond_to_questions(request: RespondRequest) -> RespondResponseV2:
    """
    Submit responses to clarification questions (v2).

    Processes user responses and either returns the next round of questions
    or the final collected data if clarification is complete.

    Args:
        request: Response submission with session ID and answers

    Returns:
        Next questions, state, and data object (or final data if complete)
    """
    # Start API timing
    api_start_time = time.perf_counter()

    session_id = request.session_id

    # Check session exists
    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    session = _sessions[session_id]

    # Get debug logger from registry (same instance used across all calls)
    debug_logger = get_or_create_logger(session_id)
    current_state = session["state"]
    config = session["config"]
    current_round = current_state["current_round"]

    # Check if already complete
    if current_state.get("clarification_complete", False):
        api_duration_ms = (time.perf_counter() - api_start_time) * 1000
        debug_logger.log_api_timing(
            endpoint="/api/clarification/respond",
            duration_ms=api_duration_ms,
            round_num=current_round,
            success=True,
        )
        data_info = current_state.get("data", {})
        state_info = current_state.get("current_questions", {}).get("state", {})
        return RespondResponseV2(
            session_id=session_id,
            complete=True,
            round=current_round,
            questions=[],
            state=QuestionsStateV2(
                collected=state_info.get("collected", []),
                missing_tier1=state_info.get("missing_tier1", []),
                missing_tier2=state_info.get("missing_tier2", []),
                conflicts_detected=state_info.get("conflicts_detected", []),
                score=state_info.get("score", current_state.get("completeness_score", 100)),
            ),
            data=ClarificationDataV2(**data_info) if data_info else ClarificationDataV2(),
        )

    # V2: Merge responses into cumulative data object (server-side merging)
    current_data = current_state.get("data") or get_initial_data_object()
    merged_data = merge_user_responses_into_data(current_data, request.responses)

    # Also merge with collected_data for backwards compatibility
    new_collected_data = merge_collected_data(
        current_state.get("collected_data", {}),
        request.responses,
    )

    # Prepare next state (include session_id for debug logging in nodes)
    next_round = current_round + 1
    next_state = {
        "user_response": request.responses,
        "collected_data": new_collected_data,
        "data": merged_data,  # V2: Pass merged data to LLM
        "current_round": next_round,
        "current_questions": None,
        "session_id": session_id,
    }

    # Continue graph execution
    graph = get_graph()

    try:
        result = graph.invoke(next_state, config)

        if result is None:
            api_duration_ms = (time.perf_counter() - api_start_time) * 1000
            debug_logger.log_api_timing(
                endpoint="/api/clarification/respond",
                duration_ms=api_duration_ms,
                round_num=next_round,
                success=False,
                error="Graph execution failed",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Graph execution failed",
            )

        # Update session state
        _sessions[session_id]["state"] = result

        # Extract v2 questions data
        questions_data = result.get("current_questions", {})
        state_info = questions_data.get("state", {})
        data_info = questions_data.get("data", result.get("data", {}))

        # Check if complete
        if result.get("clarification_complete", False):
            api_duration_ms = (time.perf_counter() - api_start_time) * 1000
            debug_logger.log_api_timing(
                endpoint="/api/clarification/respond",
                duration_ms=api_duration_ms,
                round_num=next_round,
                success=True,
            )
            # Log session summary when clarification completes
            debug_logger.log_session_summary(total_rounds=next_round)
            # Clean up logger from registry to free memory
            remove_logger(session_id)
            return RespondResponseV2(
                session_id=session_id,
                complete=True,
                round=questions_data.get("round", next_round),
                questions=[],
                state=QuestionsStateV2(
                    collected=state_info.get("collected", []),
                    missing_tier1=state_info.get("missing_tier1", []),
                    missing_tier2=state_info.get("missing_tier2", []),
                    conflicts_detected=state_info.get("conflicts_detected", []),
                    score=state_info.get("score", 100),
                ),
                data=ClarificationDataV2(**data_info) if data_info else ClarificationDataV2(),
            )

        if not questions_data:
            api_duration_ms = (time.perf_counter() - api_start_time) * 1000
            debug_logger.log_api_timing(
                endpoint="/api/clarification/respond",
                duration_ms=api_duration_ms,
                round_num=next_round,
                success=False,
                error="No questions generated but clarification not complete",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No questions generated but clarification not complete",
            )

        # Build v2 questions
        questions = [
            QuestionV2(
                id=q["id"],
                field=q["field"],
                tier=q.get("tier", 1),
                question=q["question"],
                type=q.get("type", "single_select"),
                options=q.get("options", []),
                min_selections=q.get("min_selections"),
                max_selections=q.get("max_selections"),
                allow_custom=q.get("allow_custom", False),
            )
            for q in questions_data.get("questions", [])
        ]

        # Log successful API timing
        api_duration_ms = (time.perf_counter() - api_start_time) * 1000
        debug_logger.log_api_timing(
            endpoint="/api/clarification/respond",
            duration_ms=api_duration_ms,
            round_num=next_round,
            success=True,
        )

        return RespondResponseV2(
            session_id=session_id,
            complete=False,
            round=questions_data.get("round", next_round),
            questions=questions,
            state=QuestionsStateV2(
                collected=state_info.get("collected", []),
                missing_tier1=state_info.get("missing_tier1", []),
                missing_tier2=state_info.get("missing_tier2", []),
                conflicts_detected=state_info.get("conflicts_detected", []),
                score=state_info.get("score", 0),
            ),
            data=ClarificationDataV2(**data_info) if data_info else ClarificationDataV2(),
        )

    except HTTPException:
        raise
    except Exception as e:
        api_duration_ms = (time.perf_counter() - api_start_time) * 1000
        debug_logger.log_api_timing(
            endpoint="/api/clarification/respond",
            duration_ms=api_duration_ms,
            round_num=next_round,
            success=False,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process response: {str(e)}",
        )


@router.get("/session/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str) -> SessionStatusResponse:
    """
    Get the status of a clarification session.

    Args:
        session_id: Session identifier

    Returns:
        Session status information
    """
    if session_id not in _sessions:
        return SessionStatusResponse(
            session_id=session_id,
            exists=False,
        )

    session = _sessions[session_id]
    state = session["state"]

    return SessionStatusResponse(
        session_id=session_id,
        exists=True,
        current_round=state.get("current_round"),
        completeness_score=state.get("completeness_score"),
        clarification_complete=state.get("clarification_complete"),
    )


@router.delete("/session/{session_id}")
async def delete_session(session_id: str) -> Dict[str, str]:
    """
    Delete a clarification session.

    Args:
        session_id: Session identifier

    Returns:
        Confirmation message
    """
    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    del _sessions[session_id]

    return {"message": f"Session {session_id} deleted"}


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "clarification-agent",
    }
