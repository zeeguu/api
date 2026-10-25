#!/usr/bin/env python
"""
Apply hand-checked corrections of past validator fixes.

    python -m tools.correct_rechecked_fixes zeeguu/core/llm_services/regression/recheck/<file>.yaml
    python -m tools.correct_rechecked_fixes <file>.yaml --apply

Each correction names a validation_log fix (`log_id`) and the card it should
have been (`card: "word = translation"`). The learner's bookmark in that fix's
sentence moves to the card, as a validator FIX moves it, except that the fixed
meaning is left as it is: "côté = kant" is right in general, and other learners
study it; it was only wrong in "De son côté". Without --apply, prints what would
change and writes nothing.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

import yaml

from zeeguu.core.bookmark_operations.correct_past_fix import learners_bookmarks, move, why_not
from zeeguu.core.model.validation_log import ValidationLog

session = db.session


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corrections")
    parser.add_argument("--apply", action="store_true", help="write; without it, only print")
    args = parser.parse_args()

    with open(args.corrections) as f:
        corrections = yaml.safe_load(f)["corrections"]

    moved = skipped = 0
    for correction in corrections:
        card = correction["card"]
        word, translation = (part.strip() for part in card.split("=", 1))
        fix = session.get(ValidationLog, correction["log_id"])
        reason = why_not(fix, word, translation)
        bookmarks = [] if reason else learners_bookmarks(fix)
        if not reason and not bookmarks:
            reason = "no bookmark of the fix left in the sentence"
        if reason:
            print(f"SKIP   log {correction['log_id']}: {card} ({reason})")
            skipped += 1
            continue
        shown = f"{fix.new_meaning.origin.content} = {fix.new_meaning.translation.content} -> {card}"
        for bookmark in bookmarks:
            print(f"{'MOVE' if args.apply else 'WOULD'}  log {fix.id}: bookmark {bookmark.id} "
                  f"of user {bookmark.user_word.user_id}: {shown}")
            if args.apply:
                move(session, bookmark, fix, word, translation, card)
                session.commit()
            moved += 1

    print(f"\n{moved} {'moved' if args.apply else 'would move'}, {skipped} skipped")


if __name__ == "__main__":
    main()
