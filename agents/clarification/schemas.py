"""
Schemas for the clarification agent.

Defines the state schema for LangGraph, Pydantic models for structured
questions and responses, and API request/response models.
"""

from typing import TypedDict, List, Optional, Annotated, Dict, Any, Literal
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

    # V2: Cumulative data object returned every round
    data: Optional[dict]

    # Messages for tracking conversation history
    messages: Annotated[List[dict], operator.add]

    # Debug/tracking
    session_id: Optional[str]


# =============================================================================
# Question Models (Pydantic)
# =============================================================================


class Question(BaseModel):
    """A single clarification question (v1)."""

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
    """State information returned with questions (v1)."""

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
    Structured response from LLM containing questions (v1).

    This model validates the JSON output from the LLM during
    clarification rounds.
    """

    status: str = Field(description="Status: 'in_progress' or 'complete'")
    round: int = Field(ge=1, le=3, description="Current round number (1-3)")
    questions: List[Question] = Field(description="List of questions for this round")
    state: QuestionsState = Field(description="Current state information")


class FinalClarificationData(BaseModel):
    """
    Final collected data from clarification (v1).

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
# V2 Question Models (Pydantic)
# =============================================================================


class QuestionV2(BaseModel):
    """A single clarification question (v2)."""

    id: str = Field(description="Unique identifier in q<round>_<num> format")
    field: str = Field(description="The data field this question populates")
    tier: int = Field(ge=1, le=4, description="Question tier (1-4)")
    question: str = Field(description="The question text to display to user")
    type: Literal["single_select", "multi_select", "ranked", "text"] = Field(
        description="Question type"
    )
    options: List[str] = Field(default_factory=list, description="Available options")
    min_selections: Optional[int] = Field(
        default=None, description="Minimum selections for multi_select"
    )
    max_selections: Optional[int] = Field(
        default=None, description="Maximum selections for multi_select"
    )
    allow_custom: bool = Field(
        default=False, description="Whether custom text input is allowed"
    )


class QuestionsStateV2(BaseModel):
    """State information returned with questions (v2)."""

    collected: List[str] = Field(
        default_factory=list, description="Fields already collected"
    )
    missing_tier1: List[str] = Field(
        default_factory=list, description="Missing tier 1 fields"
    )
    missing_tier2: List[str] = Field(
        default_factory=list, description="Missing tier 2 fields"
    )
    conflicts_detected: List[str] = Field(
        default_factory=list, description="Detected conflicts between answers"
    )
    score: int = Field(default=0, ge=0, le=100, description="Current completeness score")


class Top3MustDos(BaseModel):
    """Ranked top 3 must-do activities."""

    first: Optional[str] = Field(default=None, alias="1")
    second: Optional[str] = Field(default=None, alias="2")
    third: Optional[str] = Field(default=None, alias="3")

    class Config:
        populate_by_name = True


class ClarificationDataV2(BaseModel):
    """
    Cumulative data object returned every round (v2).

    All fields are Optional - returns null for uncollected fields.
    """

    # Tier 1: Critical
    activity_preferences: Optional[List[str]] = None
    pace_preference: Optional[str] = None
    tourist_vs_local: Optional[str] = None
    mobility_level: Optional[str] = None
    dining_style: Optional[List[str]] = None

    # Tier 2: Planning Essentials
    top_3_must_dos: Optional[Dict[str, Optional[str]]] = None
    transportation_mode: Optional[List[str]] = None
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    budget_priority: Optional[str] = None
    accommodation_style: Optional[str] = None

    # Tier 3: Conditional Critical
    wifi_need: Optional[str] = None
    dietary_severity: Optional[str] = None
    special_logistics: Optional[str] = None

    # Tier 4: Optimization
    accessibility_needs: Optional[str] = None
    daily_rhythm: Optional[str] = None
    downtime_preference: Optional[str] = None

    # Meta fields
    conflicts_resolved: Optional[List[str]] = Field(default=None, alias="_conflicts_resolved")
    warnings: Optional[List[str]] = Field(default=None, alias="_warnings")

    class Config:
        populate_by_name = True


class QuestionsResponseV2(BaseModel):
    """
    Structured response from LLM containing questions (v2).

    This model validates the JSON output from the LLM during
    clarification rounds.
    """

    status: Literal["in_progress", "complete"] = Field(
        description="Status: 'in_progress' or 'complete'"
    )
    round: int = Field(ge=1, le=3, description="Current round number (1-3)")
    questions: List[QuestionV2] = Field(
        default_factory=list, description="Questions for this round (empty if complete)"
    )
    state: QuestionsStateV2 = Field(description="Current state information")
    data: ClarificationDataV2 = Field(description="Cumulative data object")


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


# =============================================================================
# V2 API Request/Response Models
# =============================================================================


class StartSessionResponseV2(BaseModel):
    """Response after starting a clarification session (v2)."""

    session_id: str = Field(description="Unique session identifier")
    round: int = Field(description="Current round number")
    questions: List[QuestionV2] = Field(description="Questions for this round")
    state: QuestionsStateV2 = Field(description="Current state information")
    data: ClarificationDataV2 = Field(description="Cumulative data object")


class RespondResponseV2(BaseModel):
    """Response after submitting answers (v2)."""

    session_id: str = Field(description="Session identifier")
    complete: bool = Field(description="Whether clarification is complete")
    round: int = Field(description="Current round number")
    questions: List[QuestionV2] = Field(
        default_factory=list, description="Next questions (empty if complete)"
    )
    state: QuestionsStateV2 = Field(description="Current state information")
    data: ClarificationDataV2 = Field(description="Cumulative data object")
