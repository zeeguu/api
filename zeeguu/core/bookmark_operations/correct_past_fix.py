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
from zeeguu.core.model.validation_log import ValidationLog


def learners_bookmarks(fix):
    """The bookmarks still on the fixed meaning in the fix's own sentence"""
    return [
        b
        for user_word in UserWord.query.filter_by(meaning_id=fix.new_meaning_id).all()
        for b in user_word.bookmarks()
        if b.get_context() == fix.context and b.translation_source != "generated_example"
    ]


def move(session, bookmark, fix, word, translation, card):
    fixed = fix.new_meaning
    old_user_word = bookmark.user_word
    target = Meaning.find_or_create(
        session, word, fixed.origin.language.code, translation, fixed.translation.language.code
    )
    target.validated = Meaning.VALID
    session.add(target)
    new_user_word = UserWord.find_or_create(session, old_user_word.user, target)

    # The learner's progress goes along only when this sentence was all there
    # was to the word; otherwise they still study the fixed meaning elsewhere
    if len(old_user_word.bookmarks()) == 1:
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
