import os

from sqlalchemy import func
from sqlalchemy.orm import aliased

from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.db import db
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.phrase import Phrase
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

VERBAL_FLASHCARDS_REQUIRE_LEVEL_3_ENV = "VERBAL_FLASHCARDS_REQUIRE_LEVEL_3"
MAX_ANSWER_VARIANTS = 20


def requires_level_3_flashcards():
    raw_value = os.environ.get(VERBAL_FLASHCARDS_REQUIRE_LEVEL_3_ENV, "true")
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


def _user_word_has_required_level(user_word):
    return not requires_level_3_flashcards() or (user_word.level or 0) >= 3


def _verbal_flashcard_from_bookmark(bookmark):
    if not bookmark or not bookmark.user_word:
        return None

    user_word = bookmark.user_word
    meaning = user_word.meaning
    if not meaning or not meaning.translation or not meaning.origin:
        return None

    prompt = meaning.translation.content
    answer = meaning.origin.content

    if not prompt or not answer:
        return None

    return {
        "id": str(bookmark.id),
        # Prompt is the translated cue; answer is the learned-language word.
        "prompt": prompt,
        "answer": answer,
    }


def _verbal_flashcard_from_user_word(user_word):
    return _verbal_flashcard_from_bookmark(user_word.preferred_bookmark)


def _add_unique_text(texts, text):
    cleaned_text = str(text or "").strip()
    if cleaned_text and cleaned_text.casefold() not in {t.casefold() for t in texts}:
        texts.append(cleaned_text)


def answer_variants_for_bookmark(bookmark):
    """
    Return learned-language answers accepted for a verbal flashcard.

    Zeeguu stores each translation pair as a Meaning. That lets the database hold
    several learned-language forms for the same translated cue, e.g. different
    inflections or article forms. The scheduled bookmark remains the primary
    answer, while scoring can accept other non-invalid meanings with the same
    prompt language and cue text.
    """
    if not bookmark or not bookmark.user_word or not bookmark.user_word.meaning:
        return []

    meaning = bookmark.user_word.meaning
    if not meaning.origin or not meaning.translation:
        return []

    variants = []
    _add_unique_text(variants, meaning.origin.content)

    origin_language_id = meaning.origin.language_id
    translation_language_id = meaning.translation.language_id
    prompt_key = meaning.translation.content.lower().strip()

    OriginPhrase = aliased(Phrase)
    TranslationPhrase = aliased(Phrase)
    if db.engine.dialect.name == "sqlite":
        translation_filter = func.lower(TranslationPhrase.content) == prompt_key
    else:
        translation_filter = TranslationPhrase.content_lower == prompt_key

    candidate_meanings = (
        Meaning.query
        .join(OriginPhrase, Meaning.origin_id == OriginPhrase.id)
        .join(TranslationPhrase, Meaning.translation_id == TranslationPhrase.id)
        .filter(OriginPhrase.language_id == origin_language_id)
        .filter(TranslationPhrase.language_id == translation_language_id)
        .filter(translation_filter)
        .filter(Meaning.validated != Meaning.INVALID)
        .order_by(Meaning.id.asc())
        .limit(MAX_ANSWER_VARIANTS)
        .all()
    )

    for candidate_meaning in candidate_meanings:
        _add_unique_text(variants, candidate_meaning.origin.content)

    return variants


def get_flashcard_collection(user):
    """
    Return Zeeguu study words as minimal verbal flashcards.
    """
    user_words = BasicSRSchedule.user_words_to_study(user)
    flashcards = []
    seen_words = set()

    for user_word in user_words:
        if not _user_word_has_required_level(user_word):
            continue

        word_text = user_word.meaning.origin.content.lower()
        if word_text in seen_words:
            continue

        card = _verbal_flashcard_from_user_word(user_word)
        if card:
            seen_words.add(word_text)
            flashcards.append(card)

    return flashcards


def find_flashcard_submission_target(user, flashcard_id):
    if not flashcard_id:
        return None

    bookmark = Bookmark.find(flashcard_id)
    if not bookmark or not bookmark.user_word or bookmark.user_word.user_id != user.id:
        return None
    if not _user_word_has_required_level(bookmark.user_word):
        return None

    return bookmark
