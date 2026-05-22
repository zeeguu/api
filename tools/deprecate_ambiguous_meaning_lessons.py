#!/usr/bin/env python
"""
Mark meaning-lesson scripts containing the ambiguous "(how|could) you say
you ..." challenge phrasing as deprecated, so future daily audio lessons
regenerate them under the new prompt that pins listener-as-speaker.

Existing daily_audio_lesson_segment rows that already reference these
audio_lesson_meaning rows keep playing as before — the cached MP3s stay
on disk; only fresh lookups via AudioLessonMeaning.find() skip them.

Usage:
    python -m tools.deprecate_ambiguous_meaning_lessons          # dry run
    python -m tools.deprecate_ambiguous_meaning_lessons --apply  # do it
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from sqlalchemy import text


AMBIGUOUS_REGEX = r"(how|could) you say you[' ]?(re| are| ll| ve)"


def main(apply: bool):
    matched = db.session.execute(
        text(
            "SELECT COUNT(*) FROM audio_lesson_meaning "
            "WHERE deprecated_at IS NULL AND script REGEXP :pattern"
        ),
        {"pattern": AMBIGUOUS_REGEX},
    ).scalar()

    print(f"Matched {matched} non-deprecated rows with ambiguous challenge phrasing.")

    if not apply:
        print("Dry run — no rows updated. Re-run with --apply to mark them deprecated.")
        return

    if matched == 0:
        print("Nothing to do.")
        return

    result = db.session.execute(
        text(
            "UPDATE audio_lesson_meaning SET deprecated_at = NOW() "
            "WHERE deprecated_at IS NULL AND script REGEXP :pattern"
        ),
        {"pattern": AMBIGUOUS_REGEX},
    )
    db.session.commit()
    print(f"Marked {result.rowcount} rows deprecated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually mark rows deprecated. Without this flag the script only reports counts.",
    )
    args = parser.parse_args()
    main(apply=args.apply)
