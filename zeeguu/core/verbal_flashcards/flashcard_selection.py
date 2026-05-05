import os

from sqlalchemy import func
from sqlalchemy.orm import aliased

from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.db import db
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.phrase import Phrase
from zeeguu.core.verbal_flashcards.fuzzy_match import (
    optimal_string_alignment_distance,
)
from zeeguu.core.verbal_flashcards.text_normalization import (
    UnsupportedLanguageError,
    normalizer_for,
)
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

VERBAL_FLASHCARDS_REQUIRE_LEVEL_3_ENV = "VERBAL_FLASHCARDS_REQUIRE_LEVEL_3"
MAX_ANSWER_VARIANTS = 20
MAX_ANSWER_VARIANT_EDIT_DISTANCE = 2


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


def _is_close_answer_variant(primary_answer, candidate_answer, language_code):
    """
    Keep database variants scoped to likely surface-form relatives.

    Matching only on translated cue text over-accepts homonyms: Danish
    "forår", "fjeder", and "kilde" can all translate to English "spring",
    but they are unrelated answers. Until Zeeguu has a meaning-family or
    inflection-group model, only accept variants that are at most two edits
    away from the scheduled answer, which keeps cases like "bold" / "bolden".
    """
    try:
        normalizer = normalizer_for(language_code)
    except UnsupportedLanguageError:
        return False

    primary_form = normalizer.canonical_form(primary_answer)
    candidate_form = normalizer.canonical_form(candidate_answer)

    return (
        optimal_string_alignment_distance(primary_form, candidate_form)
        <= MAX_ANSWER_VARIANT_EDIT_DISTANCE
    )


def answer_variants_for_bookmark(bookmark):
    """
    Return learned-language answers accepted for a verbal flashcard.

    The scheduled bookmark remains the primary answer. Other database meanings
    with the same translated cue are accepted only when their learned-language
    form is close to that primary answer, preventing unrelated homonyms from
    being accepted for the same English cue.
    """
    if not bookmark or not bookmark.user_word or not bookmark.user_word.meaning:
        return []

    meaning = bookmark.user_word.meaning
    if not meaning.origin or not meaning.translation:
        return []

    primary_answer = meaning.origin.content
    variants = []
    _add_unique_text(variants, primary_answer)

    origin_language_id = meaning.origin.language_id
    origin_language_code = meaning.origin.language.code
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
        candidate_answer = candidate_meaning.origin.content
        if _is_close_answer_variant(
            primary_answer,
            candidate_answer,
            origin_language_code,
        ):
            _add_unique_text(variants, candidate_answer)

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
