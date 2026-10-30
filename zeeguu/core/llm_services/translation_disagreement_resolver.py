"""
Asks an LLM for the translation of a looked-up word when the machine
translators disagree on it. Called from the reader right after the lookup
(/resolve_translation_disagreement), so a learner may be waiting: no retries.
"""

import json
import re
from dataclasses import dataclass

from zeeguu.core.llm_services import claude, models
from zeeguu.core.model.language import Language
from zeeguu.logging import log

TIMEOUT_SECONDS = 10


@dataclass
class Resolution:
    translation: str
    reason: str


def resolve_translation_disagreement(word, sentence, candidates, source_lang, target_lang):
    """The model's translation of ``word`` in ``sentence`` given the
    disagreeing ``candidates`` (strings), or None if it could not be asked
    in time (or at all: no API key, network down)."""
    from .prompts.translation_disagreement import (
        TRANSLATION_DISAGREEMENT_SCHEMA,
        create_translation_disagreement_prompt,
    )

    prompt = create_translation_disagreement_prompt(
        word=word,
        sentence=sentence,
        candidates=candidates,
        source_lang=Language.LANGUAGE_NAMES.get(source_lang, source_lang),
        target_lang=Language.LANGUAGE_NAMES.get(target_lang, target_lang),
    )
    model = models.TRANSLATION_DISAGREEMENT
    try:
        response = claude.shared_client(TIMEOUT_SECONDS, max_retries=0).messages.create(
            model=model,
            **claude.request_options(model),
            max_tokens=200,
            output_config={"format": {"type": "json_schema", "schema": TRANSLATION_DISAGREEMENT_SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        )
        reply = json.loads(claude.response_text(response))
    except Exception as e:
        log(f"[TRANSLATION-DISAGREEMENT] resolver failed for '{word}': {e}")
        return None

    translation = (reply.get("translation") or "").strip().strip("\"'.")
    if not translation:
        return None
    # The reason is shown as text; the model now and then ends it with a tag
    # or with the JSON's closing quote and brace.
    reason = re.sub(r"<[^>]*>", "", reply.get("reason") or "").strip().rstrip('"}').strip()
    return Resolution(translation=translation, reason=reason)
