"""
Tests for shared research-node execution helpers.
"""

from typing import Any, Dict

from pydantic import BaseModel

import agents.research.nodes.base as base_module
from agents.shared.contracts.research_output_v2 import InDestinationBudget, WeatherInfo


class _ResponseModel(BaseModel):
    """Minimal response model for fallback tests."""

    season: str


class _ResponseModelWithOpenObject(BaseModel):
    """Response model that uses an open-ended JSON object."""

    values: Dict[str, int]


class _FakeBadRequestError(Exception):
    """Stand-in for OpenAI BadRequestError in unit tests."""

    def __init__(self, message: str, param: str | None = None) -> None:
        super().__init__(message)
        self.param = param


def test_call_structured_with_fallback_uses_json_mode_on_schema_rejection(monkeypatch):
    """Schema-invalid structured parse errors should retry via JSON mode."""
    monkeypatch.setattr(base_module, "get_cached_client", lambda: object())
    monkeypatch.setattr(base_module, "BadRequestError", _FakeBadRequestError)
    captured: Dict[str, Any] = {}

    def _raise_schema_error(**_: Any):
        raise _FakeBadRequestError(
            "Invalid schema for response_format 'WeatherInfo'",
            param="response_format",
        )

    def _json_fallback(**kwargs: Any):
        captured.update(kwargs)
        return '{"season": "spring"}', {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        }

    monkeypatch.setattr(base_module, "parse_llm_response", _raise_schema_error)
    monkeypatch.setattr(base_module, "get_llm_response_with_usage", _json_fallback)

    result, usage, raw_response = base_module.call_structured_with_fallback(
        system_prompt="system",
        user_prompt="user",
        response_model=_ResponseModel,
    )

    assert result.season == "spring"
    assert usage["total_tokens"] == 15
    assert raw_response == '{"season": "spring"}'
    assert "json" in captured["user_prompt"].lower()
    assert captured["response_format"] == {"type": "json_object"}


def test_schema_rejection_detection_is_narrow():
    """Only response-format schema failures should trigger the JSON fallback."""
    original_bad_request_error = base_module.BadRequestError
    base_module.BadRequestError = _FakeBadRequestError

    schema_error = _FakeBadRequestError(
        "Invalid schema for response_format 'WeatherInfo'",
        param="response_format",
    )
    other_error = _FakeBadRequestError("Some other bad request", param="messages")

    try:
        assert base_module._should_fallback_to_json_mode(schema_error) is True
        assert base_module._should_fallback_to_json_mode(other_error) is False
    finally:
        base_module.BadRequestError = original_bad_request_error


def test_call_structured_with_fallback_skips_parse_for_open_object_schema(
    monkeypatch,
):
    """Unsupported schemas should go straight to JSON mode without a failed parse call."""
    monkeypatch.setattr(base_module, "get_cached_client", lambda: object())
    parse_called = False
    captured: Dict[str, Any] = {}

    def _parse_should_not_run(**_: Any):
        nonlocal parse_called
        parse_called = True
        raise AssertionError("parse_llm_response should not be called")

    def _json_fallback(**kwargs: Any):
        captured.update(kwargs)
        return '{"values": {"a": 1}}', {
            "input_tokens": 8,
            "output_tokens": 4,
            "total_tokens": 12,
        }

    monkeypatch.setattr(base_module, "parse_llm_response", _parse_should_not_run)
    monkeypatch.setattr(base_module, "get_llm_response_with_usage", _json_fallback)

    result, usage, raw_response = base_module.call_structured_with_fallback(
        system_prompt="system",
        user_prompt="user",
        response_model=_ResponseModelWithOpenObject,
    )

    assert parse_called is False
    assert result.values == {"a": 1}
    assert usage["total_tokens"] == 12
    assert raw_response == '{"values": {"a": 1}}'
    assert captured["response_format"] == {"type": "json_object"}


def test_supports_native_structured_output_accepts_explicit_nested_schema():
    """Explicit nested-object schemas should remain eligible for structured parsing."""

    assert base_module._supports_native_structured_output(WeatherInfo) is True
    assert base_module._supports_native_structured_output(InDestinationBudget) is True


def test_weather_info_normalizes_json_mode_variants():
    """WeatherInfo should tolerate common JSON-mode string/list omissions."""
    result = WeatherInfo.model_validate(
        {
            "destination": "Tokyo, Japan",
            "temperature_range_celsius": {"min": 11, "max": 19},
            "clothing_recommendations": "Pack light layers and a rain jacket.",
            "weather_notes": "Early April can bring mild rain.",
        }
    )

    assert result.season == "not specified"
    assert result.precipitation_likelihood == "moderate"
    assert result.clothing_recommendations == ["Pack light layers and a rain jacket."]
    assert result.weather_notes == ["Early April can bring mild rain."]


def test_budget_normalizes_missing_derived_fields_and_textual_assessment():
    """Budget validation should derive omitted fields from the provided totals."""
    result = InDestinationBudget.model_validate(
        {
            "total_available_usd": 2000,
            "trip_duration": 5,
            "breakdown": {
                "accommodation": 800,
                "food": 450,
                "activities": 500,
                "transport": 250,
            },
            "budget_assessment": "This budget supports comfortable spending.",
            "budget_tips": "Book major attractions in advance.",
        }
    )

    assert result.trip_duration_days == 5
    assert result.daily_budget_usd == 400.0
    assert result.budget_assessment == "comfortable"
    assert result.breakdown.local_transport == 250
    assert result.budget_tips == ["Book major attractions in advance."]
