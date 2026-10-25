#!/usr/bin/env python
"""
Run once after migration 26-10-25--user_word_study_choice.sql. The words whose
forced "use in exercises" (#895) was not carried over as the learner's study
choice are judged by the quality checks again; those that fail them leave
study. Prints what changes; pass --apply to write.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from sqlalchemy import text

from zeeguu.core.bookmark_quality.fit_for_study import fit_given, unfit_reason
from zeeguu.core.model.user_word import UserWord

apply = "--apply" in sys.argv

# user_preference is no longer on the model; the column is still in the table
ids = [
    row[0]
    for row in db.session.execute(
        text("SELECT id FROM user_word WHERE user_preference = '1' AND study_choice IS NULL")
    )
]
print(f"{len(ids)} words lost a forced opt-in")

leaving = failed = 0
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
        if was_fit and not now_fit:
            leaving += 1
            print(f"  {user_word.id} {user_word.meaning.origin.content!r} -> "
                  f"{user_word.meaning.translation.content!r}: {reason}", flush=True)
    except Exception as e:
        db.session.rollback()
        failed += 1
        print(f"  {user_word_id} skipped: {e}", flush=True)

print(f"{leaving} leave study, {failed} skipped{'' if apply else ' (dry run; --apply to write)'}")
