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

Classify this into one of three categories:

1. "invalid" — offensive, nonsensical, random characters, too vague (single word with no clear topic), or not something two adults could have a conversation about.

2. "niche" — a valid topic but too personal or specific for other learners. It references specific people, dates, or situations unique to the user. Examples: "my sister's wedding next Saturday", "explaining to my neighbor why my dog barks", "my thesis defense at university", "what happened at the Berlin flea market yesterday". These are fine to generate but shouldn't appear in autocomplete.

3. "general" — a topic or situation that many language learners would benefit from. Be generous here — if the user phrases a general topic personally (e.g. "talking to my boss about a raise"), it's still general (canonicalize to "asking for a raise"). Examples: "restaurant", "doctor visit", "job interview", "grocery shopping", "travel", "cooking", "meeting neighbors", "asking for a raise", "renting an apartment", "public transport".

If valid (niche or general), also produce a short canonical form (lowercase, 2-5 words, no articles at the start). Examples: "At the Restaurant" → "restaurant", "going to the doctor's office" → "doctor visit", "cooking Italian food" → "cooking italian food".

Reply with ONLY a JSON object, no other text:
{{"category": "general", "canonical": "the canonical form"}}
or
{{"category": "niche", "canonical": "the canonical form"}}
or
{{"category": "invalid", "reason": "brief reason"}}
"""


def validate_suggestion(suggestion, suggestion_type):
    """
    Validate and sanitize a user suggestion.

    Returns:
        (is_valid, result_dict) where result_dict contains:
        - If valid: {"canonical": "...", "is_general": True/False}
        - If invalid: {"reason": "..."}
    """
    if not suggestion or not suggestion.strip():
        return False, {"reason": "Empty suggestion"}

    suggestion = suggestion.strip()

    # Quick rejections without LLM
    if len(suggestion) < 2:
        return False, {"reason": "Suggestion too short"}
    if len(suggestion) > 80:
        return False, {"reason": "Suggestion too long"}

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
        category = result.get("category", "invalid")

        if category == "invalid":
            reason = result.get("reason", "Not suitable for a language lesson")
            log(f"[suggestion_validator] '{suggestion}' rejected: {reason}")
            return False, {"reason": reason}

        canonical = result.get("canonical", suggestion.lower()).strip()[:80]
        is_general = category == "general"
        log(f"[suggestion_validator] '{suggestion}' → canonical: '{canonical}' (general: {is_general})")
        return True, {"canonical": canonical, "is_general": is_general}

    except Exception as e:
        # If validation fails, let it through with basic sanitization
        log(f"[suggestion_validator] LLM validation failed, allowing with basic sanitization: {e}")
        return True, {"canonical": suggestion.strip().lower()[:80], "is_general": False}
