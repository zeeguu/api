"""
Shared client for one-shot completions against Anthropic's Haiku model.

This is the "real-time, text-simplification key" Anthropic family,
separate from the SDK-based `AnthropicService` (which uses
ANTHROPIC_API_KEY + Sonnet for background pipelines).

Two entry points:
- haiku_completion: returns None on any failure (no key, network,
  non-200, malformed payload). Use when the caller has a fail-soft
  contract — e.g. article ingestion that must not block on a flaky LLM.
- haiku_completion_or_raise: raises on failure. Use when the caller's
  contract is "this MUST succeed" — e.g. an explicit user-initiated
  correction request.
"""

import os
from typing import Optional

import requests
from zeeguu.logging import log
from zeeguu.core.llm_services import models

HAIKU_MODEL = models.ANTHROPIC_HAIKU
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def _post(prompt: str, max_tokens: int, temperature: float, timeout: int) -> requests.Response:
    api_key = os.environ.get("ANTHROPIC_TEXT_SIMPLIFICATION_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_TEXT_SIMPLIFICATION_KEY not set")
    return requests.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        },
        json={
            "model": HAIKU_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=timeout,
    )


def haiku_completion(
    prompt: str,
    max_tokens: int,
    temperature: float = 0.0,
    timeout: int = 30,
) -> Optional[str]:
    """
    POST a single-turn prompt to Haiku. Returns the response text, or
    None on any failure (key missing, network error, non-200,
    malformed payload). Logs the failure.
    """
    try:
        response = _post(prompt, max_tokens, temperature, timeout)
        if response.status_code != 200:
            log(f"Anthropic API error: {response.status_code}")
            return None
        data = response.json()
        # stop_reason "max_tokens" means the reply was cut off at the cap — the
        # text is incomplete and any caller parsing it (JSON, structured fields)
        # gets garbage. Treat truncation as a failure so callers fall back or
        # surface an error instead of promoting a half-finished result. Callers
        # that need longer output should raise max_tokens.
        if data.get("stop_reason") == "max_tokens":
            log(f"Haiku output truncated at max_tokens={max_tokens}")
            return None
        return data["content"][0]["text"]
    except Exception as e:
        log(f"Haiku completion failed: {e}")
        return None


def haiku_completion_or_raise(
    prompt: str,
    max_tokens: int,
    temperature: float = 0.0,
    timeout: int = 30,
) -> str:
    """
    POST a single-turn prompt to Haiku. Returns the response text, or
    raises on any failure. Use when caller expects an exception.
    """
    response = _post(prompt, max_tokens, temperature, timeout)
    if response.status_code != 200:
        raise Exception(
            f"Anthropic API error: {response.status_code} - {response.text}"
        )
    # NOTE: deliberately does NOT treat stop_reason "max_tokens" as an error.
    # The fail-soft haiku_completion does (truncation -> None -> fallback), but
    # the batch crawl simplification pipeline calls this variant and has long
    # inputs that can legitimately hit the cap; raising here would turn stored
    # (truncated) simplifications into pipeline failures and shrink feed
    # inventory. Left as-is on purpose — revisit alongside the chunking work.
    return response.json()["content"][0]["text"]
