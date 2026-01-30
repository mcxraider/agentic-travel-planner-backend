"""
OpenAI client with retry logic.

Provides a cached client instance and a wrapper for LLM calls with
automatic retries using tenacity.
"""

import os
from typing import List, Dict, Optional, Tuple

from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from dotenv import load_dotenv
load_dotenv()

# Module-level cache for OpenAI client
_client: Optional[OpenAI] = None


def get_cached_client() -> OpenAI:
    """
    Returns a cached instance of the OpenAI client.

    Uses OPENAI_API_KEY_1 environment variable for authentication.
    The client is created once and reused for all subsequent calls.
    """
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY_1")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY_1 environment variable is not set. "
                "Please set it to your OpenAI API key."
            )
        _client = OpenAI(api_key=api_key)
    return _client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def call_llm(
    messages: List[Dict[str, str]],
    model: str = "gpt-4.1-mini",
    client: Optional[OpenAI] = None,
) -> str:
    """
    Call the OpenAI Chat Completion API with automatic retries.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model: Model identifier to use (default: gpt-4.1-mini)
        client: Optional OpenAI client instance. If not provided, uses cached client.

    Returns:
        The assistant's response content as a string.

    Raises:
        Exception: If all retry attempts fail.
    """
    if client is None:
        client = get_cached_client()

    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    return response.choices[0].message.content.strip()


def get_llm_response(
    client: OpenAI,
    user_prompt: str,
    system_prompt: str,
    model: str = "gpt-5-mini",
) -> str:
    """
    Legacy-compatible wrapper for LLM calls.

    This function maintains backward compatibility with the original
    clarification agent interface.

    Args:
        client: OpenAI client instance
        user_prompt: The user message content
        system_prompt: The system message content
        model: Model identifier to use

    Returns:
        The assistant's response content as a string.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return call_llm(messages, model=model, client=client)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def call_llm_with_usage(
    messages: List[Dict[str, str]],
    model: str = "gpt-4.1-mini",
    client: Optional[OpenAI] = None,
) -> Tuple[str, Dict[str, int]]:
    """
    Call the OpenAI Chat Completion API and return content with token usage.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model: Model identifier to use (default: gpt-4.1-mini)
        client: Optional OpenAI client instance. If not provided, uses cached client.

    Returns:
        Tuple of (response content, usage dict with input/output/total tokens)

    Raises:
        Exception: If all retry attempts fail.
    """
    if client is None:
        client = get_cached_client()

    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    content = response.choices[0].message.content.strip()
    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }

    return content, usage


def get_llm_response_with_usage(
    client: OpenAI,
    user_prompt: str,
    system_prompt: str,
    model: str = "gpt-5-mini",
) -> Tuple[str, Dict[str, int]]:
    """
    Get LLM response with token usage information.

    This function is similar to get_llm_response but also returns
    token usage for debugging and cost tracking.

    Args:
        client: OpenAI client instance
        user_prompt: The user message content
        system_prompt: The system message content
        model: Model identifier to use

    Returns:
        Tuple of (response content, usage dict with input/output/total tokens)
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return call_llm_with_usage(messages, model=model, client=client)
