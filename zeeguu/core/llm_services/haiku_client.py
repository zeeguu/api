"""
Shared client for one-shot completions against Anthropic's Haiku model.

This is the "real-time, text-simplification key" Anthropic family
(ANTHROPIC_TEXT_SIMPLIFICATION_KEY), separate from `AnthropicService`
(which uses ANTHROPIC_API_KEY + Sonnet for background pipelines). Both go
through the Anthropic SDK and `claude.request_options` / `claude.response_text`.

Two entry points:
- haiku_completion: returns None on any failure (no key, network,
  API error, truncated reply). Use when the caller has a fail-soft
  contract — e.g. article ingestion that must not block on a flaky LLM.
- haiku_completion_or_raise: raises on failure. Use when the caller's
  contract is "this MUST succeed" — e.g. an explicit user-initiated
  correction request.
"""

import os
from typing import Optional

import anthropic

from zeeguu.logging import log
from zeeguu.core.llm_services import claude, models

HAIKU_MODEL = models.ANTHROPIC_HAIKU


def _create(
    prompt: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
    stop_sequences: Optional[list] = None,
):
    api_key = os.environ.get("ANTHROPIC_TEXT_SIMPLIFICATION_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_TEXT_SIMPLIFICATION_KEY not set")
    # No retries: `timeout` is what the caller budgets for the whole call (some
    # are fallbacks a user is waiting on), and the SDK retries timeouts too, so
    # its default of 2 would triple the wait.
    client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)
    extra = {"stop_sequences": stop_sequences} if stop_sequences else {}
    return client.messages.create(
        model=HAIKU_MODEL,
        **claude.request_options(HAIKU_MODEL),
        **claude.sampling_options(HAIKU_MODEL, temperature),
        **extra,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )


def haiku_completion(
    prompt: str,
    max_tokens: int,
    temperature: float = 0.0,
    timeout: int = 30,
) -> Optional[str]:
    """
    Send a single-turn prompt to Haiku. Returns the response text, or
    None on any failure (key missing, network error, API error,
    truncated reply). Logs the failure.
    """
    try:
        response = _create(prompt, max_tokens, temperature, timeout)
        # stop_reason "max_tokens" means the reply was cut off at the cap — the
        # text is incomplete and any caller parsing it (JSON, structured fields)
        # gets garbage. Treat truncation as a failure so callers fall back or
        # surface an error instead of promoting a half-finished result. Callers
        # that need longer output should raise max_tokens.
        if response.stop_reason == "max_tokens":
            log(f"Haiku output truncated at max_tokens={max_tokens}")
            return None
        return claude.response_text(response)
    except Exception as e:
        log(f"Haiku completion failed: {e}")
        return None


def haiku_completion_or_raise(
    prompt: str,
    max_tokens: int,
    temperature: float = 0.0,
    timeout: int = 30,
    stop_sequences: Optional[list] = None,
) -> str:
    """
    Send a single-turn prompt to Haiku. Returns the response text, or
    raises on any failure (the SDK's typed errors, e.g. APIStatusError,
    APITimeoutError). Use when caller expects an exception.

    When one of `stop_sequences` ends the reply, the matched sequence is put
    back on the end of the text (Anthropic strips it), so the caller reads the
    reply exactly as the model wrote it, just cut short.
    """
    response = _create(prompt, max_tokens, temperature, timeout, stop_sequences)
    # NOTE: deliberately does NOT treat stop_reason "max_tokens" as an error.
    # The fail-soft haiku_completion does (truncation -> None -> fallback), but
    # the batch crawl simplification pipeline calls this variant and has long
    # inputs that can legitimately hit the cap; raising here would turn stored
    # (truncated) simplifications into pipeline failures and shrink feed
    # inventory. Left as-is on purpose — revisit alongside the chunking work.
    text = claude.response_text(response)
    if response.stop_reason == "stop_sequence" and response.stop_sequence:
        text += response.stop_sequence
    return text
