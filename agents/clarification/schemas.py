"""
Schemas for the clarification agent.

Defines the state schema for LangGraph, Pydantic models for structured
questions and responses, and API request/response models.
"""

from typing import TypedDict, List, Optional, Annotated, Dict, Any
from pydantic import BaseModel, Field
import operator


# =============================================================================
# LangGraph State Schema
# =============================================================================


class ClarificationState(TypedDict):
    """
    State schema for the clarification agent.

    This TypedDict defines all the data that flows through the LangGraph
    workflow during the clarification process.
    """

    # User context (pre-filled from user profile)
    user_name: str
    citizenship: str
    health_limitations: Optional[str]
    work_obligations: Optional[str]
    dietary_restrictions: Optional[str]
    specific_interests: Optional[List[str]]

    # Trip basics (pre-filled from trip configuration)
    destination: str
    destination_cities: Optional[List[str]]
    start_date: str
    end_date: str
    trip_duration: int
    budget: float
    currency: str
    travel_party: str
    budget_scope: str

    # Clarification process state
    current_round: int
    completeness_score: int
    clarification_complete: bool

    # Questions and responses
    current_questions: Optional[dict]  # JSON with questions from LLM
    user_response: Optional[dict]  # User's answers to current questions

    # Accumulated answers (built up over rounds)
    collected_data: dict

    # Messages for tracking conversation history
    messages: Annotated[List[dict], operator.add]


# =============================================================================
# Question Models (Pydantic)
# =============================================================================


class Question(BaseModel):
    """A single clarification question."""

    question_id: int = Field(description="Unique identifier for the question")
    field: str = Field(description="The data field this question populates")
    multi_select: bool = Field(
        default=False, description="Whether multiple options can be selected"
    )
    question_text: str = Field(description="The question text to display to user")
    options: List[str] = Field(description="Available answer options")
    allow_custom_input: bool = Field(
        default=False, description="Whether custom text input is allowed"
    )


class QuestionsState(BaseModel):
    """State information returned with questions."""

    answered_fields: List[str] = Field(
        default_factory=list, description="Fields already answered"
    )
    missing_fields: List[str] = Field(
        default_factory=list, description="Fields still needing answers"
    )
    completeness_score: int = Field(
        default=0, ge=0, le=100, description="Current completeness score"
    )


class QuestionsResponse(BaseModel):
    """
    Structured response from LLM containing questions.

    This model validates the JSON output from the LLM during
    clarification rounds.
    """

    status: str = Field(description="Status: 'in_progress' or 'complete'")
    round: int = Field(ge=1, le=3, description="Current round number (1-3)")
    questions: List[Question] = Field(description="List of questions for this round")
    state: QuestionsState = Field(description="Current state information")


class FinalClarificationData(BaseModel):
    """
    Final collected data from clarification.

    This model represents the complete set of user preferences
    after clarification is finished.
    """

    activity_preferences: List[str] = Field(default_factory=list)
    pace_preference: Optional[str] = None
    tourist_vs_local_preference: Optional[str] = None
    mobility_walking_capacity: Optional[str] = None
    dining_style: List[str] = Field(default_factory=list)
    primary_activity_focus: Optional[str] = None
    destination_specific_interests: List[str] = Field(default_factory=list)
    transportation_preference: List[str] = Field(default_factory=list)
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    special_logistics: Optional[str] = None
    wifi_need: Optional[str] = None
    schedule_preference: Optional[str] = None


# =============================================================================
# API Request/Response Models
# =============================================================================

# Required Type before generating AI responses (when user presses "Clarify button")
class StartSessionRequest(BaseModel):
    """Request to start a new clarification session."""

    # User profile
    user_name: str = Field(description="User's name")
    citizenship: str = Field(default="Not specified", description="User's citizenship")
    health_limitations: Optional[str] = Field(
        default=None, description="Any health/mobility limitations"
    )
    work_obligations: Optional[str] = Field(
        default=None, description="Work obligations during trip"
    )
    dietary_restrictions: Optional[str] = Field(
        default=None, description="Dietary restrictions"
    )
    specific_interests: Optional[List[str]] = Field(
        default=None, description="Specific interests or must-sees"
    )

    # Trip details
    destination: str = Field(description="Trip destination")
    destination_cities: Optional[List[str]] = Field(
        default=None, description="Specific cities to visit"
    )
    start_date: str = Field(description="Trip start date (YYYY-MM-DD)")
    end_date: str = Field(description="Trip end date (YYYY-MM-DD)")
    budget: float = Field(gt=0, description="Trip budget")
    currency: str = Field(default="USD", description="Budget currency")
    travel_party: str = Field(default="1 adult", description="Who is traveling")
    budget_scope: str = Field(
        default="Total trip budget", description="What budget covers"
    )


class StartSessionResponse(BaseModel):
    """Response after starting a clarification session."""

    session_id: str = Field(description="Unique session identifier")
    round: int = Field(description="Current round number")
    questions: List[Question] = Field(description="Questions for this round")
    state: QuestionsState = Field(description="Current state information")


class RespondRequest(BaseModel):
    """Request to submit responses to questions."""

    session_id: str = Field(description="Session identifier")
    responses: Dict[str, Any] = Field(
        description="Map of field names to user responses"
    )


class RespondResponse(BaseModel):
    """Response after submitting answers."""

    session_id: str = Field(description="Session identifier")
    complete: bool = Field(description="Whether clarification is complete")
    round: Optional[int] = Field(
        default=None, description="Current round (if not complete)"
    )
    questions: Optional[List[Question]] = Field(
        default=None, description="Next questions (if not complete)"
    )
    state: Optional[QuestionsState] = Field(
        default=None, description="Current state (if not complete)"
    )
    collected_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Final collected data (if complete)"
    )


class SessionStatusResponse(BaseModel):
    """Response for session status query."""

    session_id: str
    exists: bool
    current_round: Optional[int] = None
    completeness_score: Optional[int] = None
    clarification_complete: Optional[bool] = None
