"""
Validates and sanitizes user-provided topic/situation suggestions for audio lessons.
Uses an LLM to classify whether the input is appropriate and to produce a canonical form.
"""

import json
from zeeguu.core.llm_services import get_llm_service
from zeeguu.logging import log

VALIDATION_PROMPT = """You are a content classifier for a language learning app. A user wants to generate a listening lesson about a topic or situation.

The user typed: "{suggestion}"
The type is: "{suggestion_type}"

Your job:
1. Is this a reasonable topic or situation for a language learning dialogue? It should be something two adults could have a conversation about. Reject anything offensive, nonsensical, or too vague (e.g. just a single letter or random characters).
2. If valid, produce a short canonical form (lowercase, 2-5 words, no articles at the start). For example: "At the Restaurant" → "restaurant", "going to the doctor's office" → "doctor visit", "cooking Italian food" → "cooking italian food".

Reply with ONLY a JSON object, no other text:
{{"valid": true, "canonical": "the canonical form"}}
or
{{"valid": false, "reason": "brief reason"}}
"""


def validate_suggestion(suggestion, suggestion_type):
    """
    Validate and sanitize a user suggestion.

    Returns:
        (is_valid, canonical_or_reason)
        - If valid: (True, "canonical form")
        - If invalid: (False, "reason for rejection")
    """
    if not suggestion or not suggestion.strip():
        return False, "Empty suggestion"

    suggestion = suggestion.strip()

    # Quick rejections without LLM
    if len(suggestion) < 2:
        return False, "Suggestion too short"
    if len(suggestion) > 80:
        return False, "Suggestion too long"

    try:
        llm = get_llm_service("unified")
        prompt = VALIDATION_PROMPT.format(
            suggestion=suggestion,
            suggestion_type=suggestion_type or "topic",
        )
        response = llm.generate_text(prompt, max_tokens=100, temperature=0.0)

        # Parse the JSON response
        response = response.strip()
        # Handle potential markdown code block wrapping
        if response.startswith("```"):
            response = response.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(response)

        if result.get("valid"):
            canonical = result.get("canonical", suggestion.lower()).strip()[:80]
            log(f"[suggestion_validator] '{suggestion}' → canonical: '{canonical}'")
            return True, canonical
        else:
            reason = result.get("reason", "Not suitable for a language lesson")
            log(f"[suggestion_validator] '{suggestion}' rejected: {reason}")
            return False, reason

    except Exception as e:
        # If validation fails, let it through with basic sanitization
        log(f"[suggestion_validator] LLM validation failed, allowing with basic sanitization: {e}")
        return True, suggestion.strip().lower()[:80]
