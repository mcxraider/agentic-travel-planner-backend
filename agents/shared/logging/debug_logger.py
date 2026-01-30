"""
Debug logger for tracking LLM calls, API timing, and costs.

Writes per-session JSON log files to the logs/ directory.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# Token pricing per 1M tokens
MODEL_COSTS = {
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
    "gpt-4-mini": {"input": 0.40, "output": 1.60},
}

# Session-based logger registry to ensure same instance is reused
_logger_registry: Dict[str, "DebugLogger"] = {}


def get_or_create_logger(session_id: str, logs_dir: str = "logs") -> "DebugLogger":
    """
    Get an existing logger for the session or create a new one.
    
    This ensures the same DebugLogger instance is used across all
    API calls and graph nodes for a given session, allowing proper
    accumulation of token counts and costs.
    
    Args:
        session_id: Unique session identifier
        logs_dir: Directory to store log files (default: "logs")
        
    Returns:
        DebugLogger instance for this session
    """
    if session_id not in _logger_registry:
        _logger_registry[session_id] = DebugLogger(session_id, logs_dir)
    return _logger_registry[session_id]


def remove_logger(session_id: str) -> None:
    """
    Remove a logger from the registry (e.g., after session ends).
    
    Args:
        session_id: Session ID to remove
    """
    _logger_registry.pop(session_id, None)


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate the cost of an LLM call based on token usage.

    Args:
        model: Model identifier (e.g., "gpt-5-mini")
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens

    Returns:
        Cost in USD
    """
    costs = MODEL_COSTS.get(model, {"input": 0.0, "output": 0.0})
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return input_cost + output_cost


class DebugLogger:
    """
    Debug logger that writes per-session JSON log files.

    Tracks LLM calls, API timing, token usage, and costs.
    Log files are written in JSON Lines format (one JSON object per line).
    """

    def __init__(self, session_id: str, logs_dir: str = "logs"):
        """
        Initialize the debug logger.

        Args:
            session_id: Unique session identifier
            logs_dir: Directory to store log files (default: "logs")
        """
        self.session_id = session_id
        self.logs_dir = Path(logs_dir)
        self.log_file = self.logs_dir / f"{session_id}_logs.json"

        # Ensure logs directory exists
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Session accumulators for summary
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0
        self._total_llm_duration_ms = 0.0
        self._total_api_duration_ms = 0.0
        self._llm_call_count = 0

    def _get_timestamp(self) -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()

    def _append_to_log(self, entry: Dict[str, Any]) -> None:
        """
        Append a log entry to the session log file.

        Args:
            entry: Dictionary to write as JSON
        """
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def log_llm_call(
        self,
        round_num: int,
        system_prompt: str,
        user_prompt: str,
        response: str,
        duration_ms: float,
        input_tokens: int,
        output_tokens: int,
        model: str = "gpt-5-mini",
    ) -> None:
        """
        Log an LLM call with prompts, response, timing, and token usage.

        Args:
            round_num: Current clarification round number
            system_prompt: System prompt sent to the model
            user_prompt: User prompt sent to the model
            response: Model's response
            duration_ms: Time taken for the LLM call in milliseconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model identifier
        """
        cost = calculate_cost(model, input_tokens, output_tokens)

        # Update accumulators
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_cost += cost
        self._total_llm_duration_ms += duration_ms
        self._llm_call_count += 1

        entry = {
            "type": "llm_call",
            "timestamp": self._get_timestamp(),
            "session_id": self.session_id,
            "round": round_num,
            "model": model,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "response": response,
            "duration_ms": round(duration_ms, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": round(cost, 6),
        }

        self._append_to_log(entry)

    def log_api_timing(
        self,
        endpoint: str,
        duration_ms: float,
        round_num: Optional[int] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Log API endpoint timing.

        Args:
            endpoint: API endpoint path (e.g., "/api/clarification/start")
            duration_ms: Total time for the API call in milliseconds
            round_num: Current round number (if applicable)
            success: Whether the API call succeeded
            error: Error message if the call failed
        """
        self._total_api_duration_ms += duration_ms

        entry = {
            "type": "api_timing",
            "timestamp": self._get_timestamp(),
            "session_id": self.session_id,
            "endpoint": endpoint,
            "duration_ms": round(duration_ms, 2),
            "success": success,
        }

        if round_num is not None:
            entry["round"] = round_num

        if error:
            entry["error"] = error

        self._append_to_log(entry)

    def log_session_summary(self, total_rounds: int) -> Dict[str, Any]:
        """
        Log and return a session summary with totals.

        Args:
            total_rounds: Total number of clarification rounds completed

        Returns:
            Summary dictionary with all totals
        """
        summary = {
            "type": "session_summary",
            "timestamp": self._get_timestamp(),
            "session_id": self.session_id,
            "total_rounds": total_rounds,
            "total_llm_calls": self._llm_call_count,
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_tokens": self._total_input_tokens + self._total_output_tokens,
            "total_cost_usd": round(self._total_cost, 6),
            "total_llm_duration_ms": round(self._total_llm_duration_ms, 2),
            "total_api_duration_ms": round(self._total_api_duration_ms, 2),
        }

        self._append_to_log(summary)
        return summary

    def get_accumulated_stats(self) -> Dict[str, Any]:
        """
        Get current accumulated statistics without logging.

        Returns:
            Dictionary with current totals
        """
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_tokens": self._total_input_tokens + self._total_output_tokens,
            "total_cost_usd": round(self._total_cost, 6),
            "total_llm_duration_ms": round(self._total_llm_duration_ms, 2),
            "total_api_duration_ms": round(self._total_api_duration_ms, 2),
            "llm_call_count": self._llm_call_count,
        }
