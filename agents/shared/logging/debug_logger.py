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


def extract_questions_from_log_file(log_file_path: str, output_path: Optional[str] = None) -> str:
    """
    Extract all questions from an existing log file and save to markdown.

    This standalone function can be used to process existing log files
    that were created before the folder-based structure was implemented.

    Args:
        log_file_path: Path to the JSON log file (JSON Lines format)
        output_path: Optional output path for the markdown file.
                     If not provided, saves alongside the log file.

    Returns:
        Path to the generated markdown file
    """
    log_path = Path(log_file_path)

    if output_path:
        questions_file = Path(output_path)
    else:
        questions_file = log_path.parent / f"{log_path.stem}_questions.md"

    all_questions = []

    # Read the log file and parse each line
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Only process llm_call entries
            if entry.get("type") != "llm_call":
                continue

            round_num = entry.get("round", 0)
            session_id = entry.get("session_id", "unknown")
            response_str = entry.get("response", "")

            # Parse the response JSON to extract questions
            try:
                response_data = json.loads(response_str)
            except json.JSONDecodeError:
                continue

            questions = response_data.get("questions", [])
            if questions:
                all_questions.append({
                    "round": round_num,
                    "session_id": session_id,
                    "questions": questions
                })

    # Get session_id from first entry if available
    session_id = all_questions[0]["session_id"] if all_questions else "unknown"

    # Write to markdown file
    with open(questions_file, "w", encoding="utf-8") as f:
        f.write(f"# Questions Generated - Session {session_id}\n\n")
        f.write(f"*Source: {log_path.name}*\n\n")
        f.write(f"*Generated at: {datetime.now(timezone.utc).isoformat()}*\n\n")
        f.write("---\n\n")

        question_number = 1
        for round_data in all_questions:
            round_num = round_data["round"]
            f.write(f"## Round {round_num}\n\n")

            for q in round_data["questions"]:
                q_id = q.get("id", "N/A")
                field = q.get("field", "N/A")
                tier = q.get("tier", "N/A")
                question_text = q.get("question", "N/A")
                q_type = q.get("type", "N/A")
                options = q.get("options", [])

                f.write(f"### {question_number}. {question_text}\n\n")
                f.write(f"- **ID:** `{q_id}`\n")
                f.write(f"- **Field:** `{field}`\n")
                f.write(f"- **Tier:** {tier}\n")
                f.write(f"- **Type:** {q_type}\n")

                if options:
                    f.write(f"- **Options:**\n")
                    for opt in options:
                        f.write(f"  - {opt}\n")

                f.write("\n")
                question_number += 1

        f.write("---\n")
        f.write(f"\n*Total questions: {question_number - 1}*\n")

    return str(questions_file)


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
    Each session gets its own folder containing the log file and extracted questions.
    """

    def __init__(self, session_id: str, logs_dir: str = "logs"):
        """
        Initialize the debug logger.

        Args:
            session_id: Unique session identifier
            logs_dir: Directory to store log files (default: "logs")
        """
        self.session_id = session_id
        self.base_logs_dir = Path(logs_dir)
        # Create a session-specific folder
        self.session_dir = self.base_logs_dir / session_id
        self.log_file = self.session_dir / "session_logs.json"

        # Ensure session directory exists
        self.session_dir.mkdir(parents=True, exist_ok=True)

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

    def extract_questions_to_markdown(self) -> str:
        """
        Extract all questions from LLM call responses and save to a markdown file.

        Parses the session log file, extracts questions from each llm_call entry's
        response field, and writes them to a numbered markdown file.

        Returns:
            Path to the generated markdown file
        """
        questions_file = self.session_dir / "questions.md"
        all_questions = []

        # Read the log file and parse each line
        if not self.log_file.exists():
            return str(questions_file)

        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Only process llm_call entries
                if entry.get("type") != "llm_call":
                    continue

                round_num = entry.get("round", 0)
                response_str = entry.get("response", "")

                # Parse the response JSON to extract questions
                try:
                    response_data = json.loads(response_str)
                except json.JSONDecodeError:
                    continue

                questions = response_data.get("questions", [])
                if questions:
                    all_questions.append({
                        "round": round_num,
                        "questions": questions
                    })

        # Write to markdown file
        with open(questions_file, "w", encoding="utf-8") as f:
            f.write(f"# Questions Generated - Session {self.session_id}\n\n")
            f.write(f"*Generated at: {self._get_timestamp()}*\n\n")
            f.write("---\n\n")

            question_number = 1
            for round_data in all_questions:
                round_num = round_data["round"]
                f.write(f"## Round {round_num}\n\n")

                for q in round_data["questions"]:
                    q_id = q.get("id", "N/A")
                    field = q.get("field", "N/A")
                    tier = q.get("tier", "N/A")
                    question_text = q.get("question", "N/A")
                    q_type = q.get("type", "N/A")
                    options = q.get("options", [])

                    f.write(f"### {question_number}. {question_text}\n\n")
                    f.write(f"- **ID:** `{q_id}`\n")
                    f.write(f"- **Field:** `{field}`\n")
                    f.write(f"- **Tier:** {tier}\n")
                    f.write(f"- **Type:** {q_type}\n")

                    if options:
                        f.write(f"- **Options:**\n")
                        for opt in options:
                            f.write(f"  - {opt}\n")

                    f.write("\n")
                    question_number += 1

            f.write("---\n")
            f.write(f"\n*Total questions: {question_number - 1}*\n")

        return str(questions_file)
