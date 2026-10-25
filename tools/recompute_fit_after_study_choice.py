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

leaving = 0
for user_word_id in ids:
    user_word = db.session.get(UserWord, user_word_id)
    was_fit = user_word.fit_for_study
    user_word.update_fit_for_study(db.session)
    if was_fit and not user_word.fit_for_study:
        leaving += 1
        print(f"  {user_word.id} {user_word.meaning.origin.content!r} -> "
              f"{user_word.meaning.translation.content!r}: {user_word.unfit_reason}")
    if apply:
        db.session.commit()
    else:
        db.session.rollback()

print(f"{leaving} leave study{'' if apply else ' (dry run; --apply to write)'}")
