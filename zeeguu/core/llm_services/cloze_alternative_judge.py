"""
Asks an LLM whether a word a learner typed into a cloze also fits the blank.
Callers go through zeeguu.core.exercises.cloze_alternatives, which stores the
verdicts so each (meaning, typed word) is judged once for everybody.
"""

import json
import os
from dataclasses import dataclass

from zeeguu.core.llm_services import claude, models
from zeeguu.core.model.language import Language
from zeeguu.logging import log

# A learner is waiting with the exercise open. Past this, the answer is judged
# the way it always was (wrong), which is no worse than before.
TIMEOUT_SECONDS = 6


@dataclass
class ClozeAlternativeVerdict:
    relation: str  # MeaningAlternative.RELATIONS
    context_specific: bool
    explanation: str


class ClozeAlternativeJudge:
    MODEL_NAME = models.CLOZE_ALTERNATIVE_JUDGE

    def __init__(self):
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=0)

    def judge(self, expected, typed, translation, blanked, source_lang, target_lang):
        """The verdict, or None if the model could not be asked in time."""
        from .prompts.cloze_alternative import CLOZE_ALTERNATIVE_SCHEMA, create_cloze_alternative_prompt

        prompt = create_cloze_alternative_prompt(
            expected=expected,
            typed=typed,
            translation=translation,
            blanked=blanked,
            source_lang=Language.LANGUAGE_NAMES.get(source_lang, source_lang),
            target_lang=Language.LANGUAGE_NAMES.get(target_lang, target_lang),
        )
        try:
            response = self.client.messages.create(
                model=self.MODEL_NAME,
                **claude.request_options(self.MODEL_NAME),
                max_tokens=300,
                output_config={"format": {"type": "json_schema", "schema": CLOZE_ALTERNATIVE_SCHEMA}},
                messages=[{"role": "user", "content": prompt}],
            )
            reply = json.loads(claude.response_text(response))
        except Exception as e:
            log(f"[CLOZE-ALTERNATIVE] judge failed for '{typed}' vs '{expected}': {e}")
            return None

        return ClozeAlternativeVerdict(
            relation=reply["relation"],
            context_specific=bool(reply["context_specific"]),
            explanation=(reply.get("explanation") or "").strip(),
        )
