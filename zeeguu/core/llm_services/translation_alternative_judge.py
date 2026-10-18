"""
Asks an LLM whether a translation a learner typed for a word is also right.
Callers go through zeeguu.core.exercises.cloze_alternatives
(judge_translation_alternative), which stores the verdicts so each
(meaning, typed translation) is judged once.
"""

import json

from zeeguu.core.llm_services import claude, models
from zeeguu.core.llm_services.cloze_alternative_judge import TIMEOUT_SECONDS, ClozeAlternativeVerdict
from zeeguu.core.model.language import Language
from zeeguu.logging import log


class TranslationAlternativeJudge:
    MODEL_NAME = models.TRANSLATION_ALTERNATIVE_JUDGE

    def judge(self, word, expected, typed, sentence, source_lang, target_lang):
        """The verdict, or None if the model could not be asked in time (or at
        all: no API key, network down)."""
        from .prompts.translation_alternative import (
            TRANSLATION_ALTERNATIVE_SCHEMA,
            create_translation_alternative_prompt,
        )

        prompt = create_translation_alternative_prompt(
            word=word,
            expected=expected,
            typed=typed,
            sentence=sentence,
            source_lang=Language.LANGUAGE_NAMES.get(source_lang, source_lang),
            target_lang=Language.LANGUAGE_NAMES.get(target_lang, target_lang),
        )
        try:
            response = claude.shared_client(TIMEOUT_SECONDS, max_retries=0).messages.create(
                model=self.MODEL_NAME,
                **claude.request_options(self.MODEL_NAME),
                max_tokens=300,
                output_config={"format": {"type": "json_schema", "schema": TRANSLATION_ALTERNATIVE_SCHEMA}},
                messages=[{"role": "user", "content": prompt}],
            )
            reply = json.loads(claude.response_text(response))
        except Exception as e:
            log(f"[TRANSLATION-ALTERNATIVE] judge failed for '{typed}' vs '{expected}': {e}")
            return None

        return ClozeAlternativeVerdict(
            relation=reply["relation"],
            context_specific=bool(reply["context_specific"]),
            explanation=(reply.get("explanation") or "").strip(),
        )
