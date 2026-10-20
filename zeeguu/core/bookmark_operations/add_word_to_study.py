"""
Add a word or expression to a learner's study list, with a context sentence, and
schedule it for exercises right away.

Used by /add_custom_word (a learner typing a word in), /add_word_to_learning
(a learning card the LLM prepared for a word the learner chose) and the A0
audio lessons (the words a lesson taught the learner to say).

The find_or_create helpers below commit the session themselves, so nothing here
can be undone afterwards: everything that can refuse a word is checked before
anything is created.
"""

from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.word_scheduling import BasicSRSchedule
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord


class WordNotInContext(Exception):
    """The word does not appear exactly once in the context sentence, so the
    exercises could not tell which occurrence to point at."""

    def __init__(self, error_type, message):
        super().__init__(message)
        self.error_type = error_type  # "not_found" | "multiple_occurrences" | "tokenization_failed"
        self.message = message


def word_position_in(word, context, from_lang):
    """The word's position in `context`; WordNotInContext unless it is there exactly once."""
    from zeeguu.core.tokenization.word_position_finder import validate_single_occurrence

    validation = validate_single_occurrence(word, context, from_lang)
    if not validation["valid"]:
        raise WordNotInContext(validation["error_type"], validation["error_message"])
    return validation["position_data"]


def add_word_to_study(
    db_session,
    user,
    word,
    translation,
    from_lang_code,
    to_lang_code,
    context="",
    from_audio_lesson=False,
    translation_service=None,
):
    """
    Returns (bookmark, user_word, schedule). schedule is None when scheduling
    refused the word -- the translation failed validation, or the learner
    already studies an equivalent meaning; user_word is then not forced into
    study. Raises WordNotInContext, before anything is created.

    from_audio_lesson: the word comes from an A0 lesson, not from the learner
    typing it in. It is recorded as such (not is_user_added, an "audio_lesson"
    interaction), and it only adds a word the learner has never studied,
    learned or decided about -- lessons repeat earlier words on purpose, and
    must neither set them back to level 1 nor undo a "don't use in exercises"
    or "I know this". Returns (None, user_word, None) for a word left alone. A
    word looked up once and never touched since is taken. At the learner's own
    "max words to practise" it is added but not scheduled yet; the usual
    scheduling takes it when there is room.

    translation_service: who produced the translation (a TranslationService
    name); by default the learner (MANUAL) or the audio lesson.
    """
    from zeeguu.core.model import Bookmark, Language, Meaning, TranslationService, UserPreference
    from zeeguu.core.model.user_word import UserWord
    from zeeguu.core.model.user_word_interaction_history import UserWordInteractionHistory

    from_lang = Language.find(from_lang_code)
    if not context:
        context = word
    position = word_position_in(word, context, from_lang)

    meaning = Meaning.find_or_create(
        db_session, word, from_lang_code, translation, to_lang_code, user=user
    )
    if from_audio_lesson:
        existing = UserWord.query.filter_by(user=user, meaning=meaning).first()
        if existing is not None and (
            BasicSRSchedule.find(existing)
            or existing.is_learned()
            or (existing.user_preference or UserWordExPreference.NO_PREFERENCE)
            != UserWordExPreference.NO_PREFERENCE
        ):
            return None, existing, None

    user_word = UserWord.find_or_create(
        db_session, user, meaning, is_user_added=not from_audio_lesson
    )
    UserWordInteractionHistory.log(
        db_session,
        user_word,
        UserWordInteractionHistory.AUDIO_LESSON
        if from_audio_lesson
        else UserWordInteractionHistory.MANUAL_ADDITION,
    )

    # Bookmark.find_or_create looks this row up and fails without it.
    ContextType.find_or_create(db_session, ContextType.USER_EDITED_TEXT, commit=False)

    bookmark = Bookmark.find_or_create(
        db_session,
        user,
        word,
        from_lang_code,
        translation,
        to_lang_code,
        context,
        None,  # article_id
        None,  # source_id
        sentence_i=position["sentence_i"],
        token_i=position["token_i"],
        total_tokens=position["total_tokens"],
        c_sentence_i=position["c_sentence_i"],
        c_token_i=position["c_token_i"],
        context_identifier=ContextIdentifier(context_type=ContextType.USER_EDITED_TEXT),
        # The closest existing value; the interaction history above says
        # whether it was typed in or taught by an audio lesson.
        translation_source="user_added",
        user_word=user_word,
        translation_service=translation_service
        or (TranslationService.AUDIO_LESSON if from_audio_lesson else TranslationService.MANUAL),
    )

    user_word.preferred_bookmark = bookmark
    # Chosen on purpose -- typed in, or taught by a lesson -- so the quality
    # checks that hide looked-up words ("too short", ...) do not apply. Set
    # only now, with the bookmark in place: a word left half-made by a failure
    # above keeps no preference, and the next lesson tries it again.
    user_word.user_preference = UserWordExPreference.USE_IN_EXERCISES
    user_word.update_fit_for_study(db_session)

    if from_audio_lesson and (
        BasicSRSchedule.scheduled_user_words_count(user, from_lang)
        >= UserPreference.get_max_words_to_schedule(user)
    ):
        db_session.add(user_word)
        return bookmark, user_word, None

    schedule = FourLevelsPerWord.find_or_create(db_session, user_word)
    if schedule is None:
        return bookmark, user_word, None

    # Validation may have settled on another user_word for a corrected meaning.
    user_word = schedule.user_word
    if not from_audio_lesson:
        # Typed in again: start it over, as /add_custom_word always has.
        user_word.level = 1
    db_session.add(user_word)
    return bookmark, user_word, schedule
