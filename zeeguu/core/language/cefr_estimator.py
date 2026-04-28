"""
Estimate a CEFR level from raw text + language code, for callers that don't
have a persisted Article object — typically the share-flow detect endpoint
where the user is waiting on a modal and we want a fast level estimate.

Tries the per-language ML classifier (Random Forest) first, then falls back
to fk_to_cefr (deterministic, language-independent). Caps the input so very
long articles don't make a synchronous user-blocking endpoint slow.
"""

from typing import Optional

from zeeguu.core.language.fk_to_cefr import fk_to_cefr
from zeeguu.core.language.ml_cefr_classifier import predict_cefr_level
from zeeguu.core.language.strategies.flesch_kincaid_difficulty_estimator import (
    FleschKincaidDifficultyEstimator,
)
from zeeguu.core.model.language import Language

# CEFR signal saturates well before this — pyphen + sent_tokenize on
# tens of thousands of words is wasted work on a hot path.
MAX_CHARS_FOR_CEFR_ESTIMATION = 5000


def estimate_cefr_for_text(content: str, language_code: str) -> Optional[str]:
    if not content or not language_code:
        return None
    language = Language.find(language_code)
    if not language:
        return None

    sample = content[:MAX_CHARS_FOR_CEFR_ESTIMATION]
    fk_difficulty = (
        FleschKincaidDifficultyEstimator
        .flesch_kincaid_readability_index(sample, language)
    )
    word_count = len(sample.split())
    return (
        predict_cefr_level(sample, language_code, fk_difficulty, word_count)
        or fk_to_cefr(fk_difficulty)
    )
