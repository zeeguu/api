import os

from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
VERBAL_FLASHCARDS_REQUIRE_LEVEL_3_ENV = "VERBAL_FLASHCARDS_REQUIRE_LEVEL_3"


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
        "prompt": prompt,
        "answer": answer,
    }


def _verbal_flashcard_from_user_word(user_word):
    return _verbal_flashcard_from_bookmark(user_word.preferred_bookmark)


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
