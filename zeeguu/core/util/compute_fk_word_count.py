import logging
from zeeguu.core.model.language import Language
from zeeguu.core.language.difficulty_estimator_factory import (
    DifficultyEstimatorFactory,
)
from zeeguu.core.tokenization import TOKENIZER_MODEL, get_tokenizer

logger = logging.getLogger(__name__)


def compute_fk_and_wordcount(content, language: Language):

    fk_estimator = DifficultyEstimatorFactory.get_difficulty_estimator("fk")
    fk_difficulty = fk_estimator.estimate_difficulty(content, language, None)

    # easier to store integer in the DB
    # otherwise we have to use Decimal, and it's not supported on all dbs
    fk_difficulty = fk_difficulty["grade"]

    try:
        tokenizer = get_tokenizer(language, TOKENIZER_MODEL)
        word_count = len(tokenizer.tokenize_text(content))
    except Exception as e:
        logger.warning(f"Tokenization failed, using word split fallback: {e}")
        # Fallback: simple whitespace word count
        word_count = len(content.split())

    return fk_difficulty, word_count
