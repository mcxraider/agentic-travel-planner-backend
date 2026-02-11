"""
Completeness scoring logic for the clarification agent.

Calculates scores based on collected data fields, handles tier classification,
and determines stopping conditions. This module replaces LLM-based scoring
with deterministic code-based calculation.
"""

from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class TierConfig:
    """
    Configuration for scoring tiers.

    Defines field names, point values, and stopping thresholds for
    the completeness scoring system.
    """

    # Tier 1: Critical (10 points each)
    TIER1_FIELDS: Tuple[str, ...] = (
        "activity_preferences",
        "pace_preference",
        "tourist_vs_local",
        "mobility_level",
        "dining_style",
    )
    TIER1_POINTS: int = 10

    # Tier 2: Planning Essentials (4 points each)
    TIER2_FIELDS: Tuple[str, ...] = (
        "top_3_must_dos",
        "transportation_mode",
        "arrival_time",
        "departure_time",
        "budget_priority",
        "accommodation_style",
    )
    TIER2_POINTS: int = 4

    # Tier 3: Conditional Critical (3 points each, escalate to Tier 1 if triggered)
    TIER3_FIELDS: Tuple[str, ...] = (
        "wifi_need",
        "dietary_severity",
        "accessibility_needs",
    )
    TIER3_POINTS: int = 3

    # Tier 4: Optimization (3 points each)
    TIER4_FIELDS: Tuple[str, ...] = (
        "special_logistics",
        "daily_rhythm",
        "downtime_preference",
    )
    TIER4_POINTS: int = 3

    # Stopping thresholds
    MIN_SCORE_FOR_COMPLETION: int = 85
    MAX_ROUNDS: int = 4


DEFAULT_TIER_CONFIG = TierConfig()


@dataclass
class ScoringResult:
    """
    Result of completeness score calculation.

    Contains the overall score and detailed breakdowns by tier,
    including which fields are answered vs missing.
    """

    score: int
    tier1_answered: List[str] = field(default_factory=list)
    tier1_missing: List[str] = field(default_factory=list)
    tier2_answered: List[str] = field(default_factory=list)
    tier2_missing: List[str] = field(default_factory=list)
    tier3_answered: List[str] = field(default_factory=list)
    tier3_missing: List[str] = field(default_factory=list)
    tier4_answered: List[str] = field(default_factory=list)
    tier4_missing: List[str] = field(default_factory=list)
    elevated_tier3_fields: List[str] = field(default_factory=list)


def is_field_answered(data: Dict[str, Any], field_name: str) -> bool:
    """
    Check if a field has been answered (non-null, non-empty).

    Args:
        data: The collected data dictionary
        field_name: Field name to check

    Returns:
        True if field has a meaningful value
    """
    value = data.get(field_name)

    if value is None:
        return False

    if isinstance(value, str) and not value.strip():
        return False

    if isinstance(value, (list, dict)) and len(value) == 0:
        return False

    # Special case for top_3_must_dos - check if at least one rank is filled
    if field_name == "top_3_must_dos" and isinstance(value, dict):
        return any(v for v in value.values() if v)

    return True


def get_elevated_tier3_fields(
    work_obligations: Optional[str] = None,
    dietary_restrictions: Optional[str] = None,
    health_limitations: Optional[str] = None,
) -> List[str]:
    """
    Determine which Tier 3 fields should be elevated to Tier 1 priority.

    Tier 3 fields become critical (worth Tier 1 points) when their
    corresponding user profile conditions are met.

    Args:
        work_obligations: User's work obligations (if any)
        dietary_restrictions: User's dietary restrictions (if any)
        health_limitations: User's health limitations (if any)

    Returns:
        List of Tier 3 field names that should be treated as critical
    """
    elevated = []

    if work_obligations and work_obligations.strip():
        elevated.append("wifi_need")

    if dietary_restrictions and dietary_restrictions.strip():
        elevated.append("dietary_severity")

    if health_limitations and health_limitations.strip():
        elevated.append("accessibility_needs")

    return elevated


def calculate_completeness_score(
    data: Dict[str, Any],
    work_obligations: Optional[str] = None,
    dietary_restrictions: Optional[str] = None,
    health_limitations: Optional[str] = None,
    config: TierConfig = DEFAULT_TIER_CONFIG,
) -> ScoringResult:
    """
    Calculate the completeness score based on collected data.

    Formula: Score = (Tier1_answered * 10) + (Tier2_answered * 4)
                   + (Tier3_answered * 3 or 10 if elevated) + (Tier4_answered * 3)

    Tier 3 fields are elevated to Tier 1 scoring if their trigger condition is met.

    Args:
        data: The collected data dictionary
        work_obligations: User's work obligations for Tier 3 elevation
        dietary_restrictions: User's dietary restrictions for Tier 3 elevation
        health_limitations: User's health limitations for Tier 3 elevation
        config: Scoring configuration

    Returns:
        ScoringResult with score and field breakdowns
    """
    # Determine which Tier 3 fields are elevated
    elevated = get_elevated_tier3_fields(
        work_obligations, dietary_restrictions, health_limitations
    )

    # Calculate Tier 1
    tier1_answered = [f for f in config.TIER1_FIELDS if is_field_answered(data, f)]
    tier1_missing = [f for f in config.TIER1_FIELDS if f not in tier1_answered]

    # Calculate Tier 2
    tier2_answered = [f for f in config.TIER2_FIELDS if is_field_answered(data, f)]
    tier2_missing = [f for f in config.TIER2_FIELDS if f not in tier2_answered]

    # Calculate Tier 3
    tier3_answered = [f for f in config.TIER3_FIELDS if is_field_answered(data, f)]
    tier3_missing = [f for f in config.TIER3_FIELDS if f not in tier3_answered]

    # Calculate Tier 4
    tier4_answered = [f for f in config.TIER4_FIELDS if is_field_answered(data, f)]
    tier4_missing = [f for f in config.TIER4_FIELDS if f not in tier4_answered]

    # Calculate score with elevation consideration
    score = 0

    # Tier 1 base score
    score += len(tier1_answered) * config.TIER1_POINTS

    # Tier 2 score
    score += len(tier2_answered) * config.TIER2_POINTS

    # Tier 3 score (elevated fields count as Tier 1 points)
    for field_name in tier3_answered:
        if field_name in elevated:
            score += config.TIER1_POINTS  # Elevated to Tier 1 value
        else:
            score += config.TIER3_POINTS

    # Tier 4 score
    score += len(tier4_answered) * config.TIER4_POINTS

    return ScoringResult(
        score=min(score, 100),  # Cap at 100
        tier1_answered=tier1_answered,
        tier1_missing=tier1_missing,
        tier2_answered=tier2_answered,
        tier2_missing=tier2_missing,
        tier3_answered=tier3_answered,
        tier3_missing=tier3_missing,
        tier4_answered=tier4_answered,
        tier4_missing=tier4_missing,
        elevated_tier3_fields=elevated,
    )


def should_complete_clarification(
    scoring_result: ScoringResult,
    current_round: int,
    conflicts_detected: Optional[List[str]] = None,
    config: TierConfig = DEFAULT_TIER_CONFIG,
) -> Tuple[bool, str]:
    """
    Determine if clarification should be marked complete.

    Stopping conditions (ANY of):
    1. Round >= MAX_ROUNDS (force complete)
    2. Score >= 85 AND all Tier 1 complete AND no unresolved conflicts
    3. Score >= 85 (even if Tier 2 incomplete)

    Args:
        scoring_result: Result from calculate_completeness_score
        current_round: Current round number
        conflicts_detected: List of unresolved conflicts
        config: Scoring configuration

    Returns:
        Tuple of (should_complete: bool, reason: str)
    """
    if conflicts_detected is None:
        conflicts_detected = []

    score = scoring_result.score
    tier1_complete = len(scoring_result.tier1_missing) == 0

    # Check elevated Tier 3 fields (they're effectively Tier 1)
    elevated_missing = [
        f
        for f in scoring_result.elevated_tier3_fields
        if f in scoring_result.tier3_missing
    ]
    all_critical_complete = tier1_complete and len(elevated_missing) == 0

    no_conflicts = len(conflicts_detected) == 0

    # Condition 1: Max rounds reached (always stop)
    if current_round >= config.MAX_ROUNDS:
        return True, f"Max rounds ({config.MAX_ROUNDS}) reached"

    # Condition 2: High score + all Tier 1 complete + no conflicts
    if (
        score >= config.MIN_SCORE_FOR_COMPLETION
        and all_critical_complete
        and no_conflicts
    ):
        return (
            True,
            f"Score {score} >= {config.MIN_SCORE_FOR_COMPLETION}, "
            f"all critical fields complete, no conflicts",
        )

    # Condition 3: High score (even if Tier 2 incomplete)
    if score >= config.MIN_SCORE_FOR_COMPLETION:
        return True, f"Score {score} >= {config.MIN_SCORE_FOR_COMPLETION}"

    return False, f"Score {score} < {config.MIN_SCORE_FOR_COMPLETION}, continuing"
