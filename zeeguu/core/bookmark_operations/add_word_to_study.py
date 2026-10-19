"""
Add a word or expression to a learner's study list, with a context sentence, and
schedule it for exercises right away.

The one way to do it: /add_custom_word (a learner typing a word in) and the A0
audio lessons (the words a learner was taught to say) both come through here.
"""

from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord


class WordNotInContext(Exception):
    """The word does not appear exactly once in the context sentence, so the
    exercises could not tell which occurrence to point at."""

    def __init__(self, error_type, message):
        super().__init__(message)
        self.error_type = error_type  # "not_found" | "multiple_occurrences" | "tokenization_failed"
        self.message = message


def add_word_to_study(db_session, user, word, translation, from_lang_code, to_lang_code, context=""):
    """
    Returns (bookmark, user_word), the word scheduled at level 1. Raises
    WordNotInContext. Does not commit: the caller's unit of work does.
    """
    from zeeguu.core.model import Bookmark, Language, Meaning
    from zeeguu.core.model.user_word import UserWord
    from zeeguu.core.model.user_word_interaction_history import UserWordInteractionHistory
    from zeeguu.core.model.bookmark_context import BookmarkContext
    from zeeguu.core.tokenization.word_position_finder import validate_single_occurrence

    from_lang = Language.find(from_lang_code)

    meaning = Meaning.find_or_create(
        db_session, word, from_lang_code, translation, to_lang_code, user=user
    )
    user_word = UserWord.find_or_create(db_session, user, meaning, is_user_added=True)

    # Added on purpose, so the quality checks that hide words do not apply.
    UserWordInteractionHistory.log(
        db_session, user_word, UserWordInteractionHistory.MANUAL_ADDITION
    )
    user_word.user_preference = UserWordExPreference.USE_IN_EXERCISES
    user_word.update_fit_for_study(db_session)

    if not context:
        context = word

    context_type = ContextType.find_or_create(
        db_session, ContextType.USER_EDITED_TEXT, commit=False
    )
    BookmarkContext.find_or_create(
        db_session, context, context_type.type, from_lang, None, None, False, False
    )

    validation = validate_single_occurrence(word, context, from_lang)
    if not validation["valid"]:
        raise WordNotInContext(validation["error_type"], validation["error_message"])
    position = validation["position_data"]

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
        translation_source="user_added",
    )

    user_word.preferred_bookmark = bookmark
    FourLevelsPerWord.find_or_create(db_session, user_word)
    user_word.fit_for_study = True
    user_word.level = 1
    db_session.add(user_word)

    return bookmark, user_word
