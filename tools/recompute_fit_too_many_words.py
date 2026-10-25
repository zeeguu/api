#!/usr/bin/env python
"""
Run once after three-word expressions became studiable (origin_has_too_many_words
allows up to three words, and set phrases of any length). The words kept out
for too many words are judged by the quality checks again. Prints what
changes; pass --apply to write.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.bookmark_quality.fit_for_study import fit_given, unfit_reason
from zeeguu.core.model.study_choice import UnfitReason
from zeeguu.core.model.user_word import UserWord

apply = "--apply" in sys.argv

ids = [
    user_word_id
    for (user_word_id,) in db.session.query(UserWord.id).filter(
        UserWord.unfit_reason == UnfitReason.TOO_MANY_WORDS
    )
]
print(f"{len(ids)} words kept out for too many words")

returning = failed = 0
for user_word_id in ids:
    try:
        user_word = db.session.get(UserWord, user_word_id)
        was_fit = user_word.fit_for_study
        if apply:
            user_word.update_fit_for_study(db.session)
            reason, now_fit = user_word.unfit_reason, user_word.fit_for_study
            db.session.commit()
        else:
            # Worked out without update_fit_for_study: clearing a schedule commits
            reason = unfit_reason(user_word)
            now_fit = fit_given(user_word.study_choice, reason)
        if now_fit and not was_fit:
            returning += 1
            print(f"  {user_word.id} {user_word.meaning.origin.content!r} -> "
                  f"{user_word.meaning.translation.content!r}", flush=True)
        elif reason == UnfitReason.TOO_MANY_WORDS:
            print(f"  {user_word.id} {user_word.meaning.origin.content!r} stays out", flush=True)
    except Exception as e:
        db.session.rollback()
        failed += 1
        print(f"  {user_word_id} skipped: {e}", flush=True)

print(f"{returning} return to study, {failed} skipped{'' if apply else ' (dry run; --apply to write)'}")
