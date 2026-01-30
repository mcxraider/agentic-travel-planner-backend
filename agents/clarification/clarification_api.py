"""
FastAPI endpoints for the clarification agent.

Provides REST API for starting clarification sessions, submitting
responses, and managing session state.
"""

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
)
from agents.clarification.graph.build import create_clarification_graph
from agents.clarification.response_parser import merge_collected_data


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


def create_initial_state(request: StartSessionRequest) -> ClarificationState:
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
        "messages": [],
    }


@router.post("/start", response_model=StartSessionResponse)
async def start_session(request: StartSessionRequest) -> StartSessionResponse:
    """
    Start a new clarification session.

    Creates a new session with the provided user and trip information,
    then runs the first clarification round to generate initial questions.

    Args:
        request: Session start request with user/trip details

    Returns:
        Session ID and first round of questions
    """
    # Generate session ID
    session_id = str(uuid.uuid4())

    # Create initial state
    initial_state = create_initial_state(request)

    # Get graph and run first round
    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}

    try:
        # calls the graph, for the current state
        result = graph.invoke(initial_state, config)

        if result is None:
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

        # Extract questions from result
        questions_data = result.get("current_questions", {})

        if not questions_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No questions generated in first round",
            )

        # Build response
        questions = [
            Question(
                question_id=q["question_id"],
                field=q["field"],
                multi_select=q.get("multi_select", False),
                question_text=q["question_text"],
                options=q["options"],
                allow_custom_input=q.get("allow_custom_input", False),
            )
            for q in questions_data.get("questions", [])
        ]

        state_info = questions_data.get("state", {})
        print(result)
        return StartSessionResponse(
            session_id=session_id,
            round=questions_data.get("round", 1),
            questions=questions,
            state=QuestionsState(
                answered_fields=state_info.get("answered_fields", []),
                missing_fields=state_info.get("missing_fields", []),
                completeness_score=state_info.get("completeness_score", 0),
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start session: {str(e)}",
        )


@router.post("/respond", response_model=RespondResponse)
async def respond_to_questions(request: RespondRequest) -> RespondResponse:
    """
    Submit responses to clarification questions.

    Processes user responses and either returns the next round of questions
    or the final collected data if clarification is complete.

    Args:
        request: Response submission with session ID and answers

    Returns:
        Next questions or final collected data
    """
    session_id = request.session_id

    # Check session exists
    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    session = _sessions[session_id]
    current_state = session["state"]
    config = session["config"]

    # Check if already complete
    if current_state.get("clarification_complete", False):
        return RespondResponse(
            session_id=session_id,
            complete=True,
            collected_data=current_state.get("collected_data", {}),
        )

    # Merge responses with collected data
    new_collected_data = merge_collected_data(
        current_state.get("collected_data", {}),
        request.responses,
    )

    # Prepare next state
    next_state = {
        "user_response": request.responses,
        "collected_data": new_collected_data,
        "current_round": current_state["current_round"] + 1,
        "current_questions": None,
    }

    # Continue graph execution
    graph = get_graph()

    try:
        result = graph.invoke(next_state, config)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Graph execution failed",
            )

        # Update session state
        _sessions[session_id]["state"] = result

        # Check if complete
        if result.get("clarification_complete", False):
            return RespondResponse(
                session_id=session_id,
                complete=True,
                collected_data=result.get("collected_data", {}),
            )

        # Return next questions
        questions_data = result.get("current_questions", {})

        if not questions_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No questions generated but clarification not complete",
            )

        questions = [
            Question(
                question_id=q["question_id"],
                field=q["field"],
                multi_select=q.get("multi_select", False),
                question_text=q["question_text"],
                options=q["options"],
                allow_custom_input=q.get("allow_custom_input", False),
            )
            for q in questions_data.get("questions", [])
        ]

        state_info = questions_data.get("state", {})

        return RespondResponse(
            session_id=session_id,
            complete=False,
            round=questions_data.get("round"),
            questions=questions,
            state=QuestionsState(
                answered_fields=state_info.get("answered_fields", []),
                missing_fields=state_info.get("missing_fields", []),
                completeness_score=state_info.get("completeness_score", 0),
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
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
