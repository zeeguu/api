from zeeguu.core.model.language import Language


def compute_fk_and_wordcount(content, language: Language):
    from zeeguu.core.language.difficulty_estimator_factory import (
        DifficultyEstimatorFactory,
    )
    from zeeguu.core.tokenization import TOKENIZER_MODEL, get_tokenizer

    fk_estimator = DifficultyEstimatorFactory.get_difficulty_estimator("fk")
    fk_difficulty = fk_estimator.estimate_difficulty(content, language, None)
    tokenizer = get_tokenizer(language, TOKENIZER_MODEL)
    # easier to store integer in the DB
    # otherwise we have to use Decimal, and it's not supported on all dbs
    fk_difficulty = fk_difficulty["grade"]
    word_count = len(tokenizer.tokenize_text(content))
    return fk_difficulty, word_count
