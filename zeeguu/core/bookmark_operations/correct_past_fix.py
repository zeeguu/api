"""
Move one learner's bookmark to another meaning, as a validator FIX does, but
without marking the meaning it leaves INVALID: used to correct a past fix that
was wrong only in that learner's sentence ("côté = kant" is right in general,
not in "De son côté"). See tools/correct_rechecked_fixes.py.
"""
from zeeguu.core.bookmark_operations.update_bookmark import (
    cleanup_old_user_word,
    transfer_learning_progress,
    validate_and_update_position,
)
from zeeguu.core.model import Meaning, UserWord
from zeeguu.core.model.validation_log import ValidationAction, ValidationLog
from zeeguu.core.tokenization.word_position_finder import validate_single_occurrence


def _own(bookmarks):
    return [b for b in bookmarks if b.translation_source != "generated_example"]


def learners_bookmarks(fix):
    """The learners' own bookmarks on the fixed meaning in the fix's sentence.
    Every one, not only the one the fix moved: the pair is wrong in that
    sentence whoever has it there. (Bookmarks don't say which fix moved them:
    translation_service only names the validator since Oct 2026.)"""
    return [
        b
        for user_word in UserWord.query.filter_by(meaning_id=fix.new_meaning_id).all()
        for b in _own(user_word.bookmarks())
        if b.get_context() == fix.context
    ]


def why_not(fix, word, translation):
    """Why the correction can't be applied, checked before anything is written
    (find_or_create commits, so a half-done move can't be rolled back); None
    when it can."""
    if fix is None or fix.action != ValidationAction.FIXED or fix.new_meaning is None:
        return "not a validator fix"
    fixed = fix.new_meaning
    if (word.lower(), translation.lower()) == (fixed.origin.content.lower(), fixed.translation.content.lower()):
        return "the card is the fixed meaning itself"
    place = validate_single_occurrence(word, fix.context, fixed.origin.language)
    if not place["valid"]:
        return f"'{word}' {place['error_type']} in the sentence"
    return None


def move(session, bookmark, fix, word, translation, card):
    """Call only when why_not() is None."""
    fixed = fix.new_meaning
    old_user_word = bookmark.user_word
    target = Meaning.find_or_create(
        session, word, fixed.origin.language.code, translation, fixed.translation.language.code
    )
    target.validated = Meaning.VALID
    session.add(target)
    new_user_word = UserWord.find_or_create(session, old_user_word.user, target)

    # The learner's progress goes along only when this was the word's only
    # sentence of their own; otherwise they still study the fixed meaning there
    if len(_own(old_user_word.bookmarks())) == 1:
        transfer_learning_progress(session, old_user_word, new_user_word, bookmark)
    bookmark.user_word_id = new_user_word.id
    session.add(bookmark)
    session.flush()
    session.expire(bookmark, ["user_word"])
    validate_and_update_position(bookmark, word, fix.context)

    if not new_user_word.preferred_bookmark_id:
        new_user_word.preferred_bookmark_id = bookmark.id
        session.add(new_user_word)
    cleanup_old_user_word(session, old_user_word, bookmark)
    session.flush()
    session.expire(new_user_word, ["preferred_bookmark"])
    new_user_word.update_fit_for_study(session)

    ValidationLog.log_fixed(
        session,
        old_meaning=fixed,
        new_meaning=target,
        user_word_id=old_user_word.id,
        reason=f"Re-check of past fixes, 25 Oct 2026: {card}",
        context=fix.context,
    )
    return new_user_word
