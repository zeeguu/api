from datetime import datetime

from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord
from zeeguu.logging import log


def _verbal_flashcard_from_bookmark(bookmark):
    if not bookmark or not bookmark.user_word:
        return None

    user_word = bookmark.user_word
    prompt = user_word.meaning.translation.content
    answer = user_word.meaning.origin.content

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
        """
        Disabled during experimentation, due to uncertainty of participants having level 3 words.
        """
        """if (user_word.level or 0) < 3:
            continue"""

        word_text = user_word.meaning.origin.content.lower()
        if word_text in seen_words:
            continue

        try:
            card = _verbal_flashcard_from_user_word(user_word)
        except Exception as e:
            log(f"Skipping verbal flashcard for user_word {user_word.id}: {e}")
            continue

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

    return bookmark


def ensure_schedule_for_verbal_flashcard(db_session, user_word):
    """
    Verbal flashcards can target words that are not currently in the
    standard exercise pipeline. Create a schedule row without resetting the level
    so the word appears in /words after it is practiced.
    """
    schedule = FourLevelsPerWord.find(user_word)
    if schedule:
        return schedule

    schedule = FourLevelsPerWord(user_word=user_word)
    schedule.next_practice_time = datetime.now()
    schedule.consecutive_correct_answers = 0
    schedule.cooling_interval = 0
    db_session.add(schedule)
    db_session.flush()
    return schedule
