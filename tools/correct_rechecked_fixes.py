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

from zeeguu.core.bookmark_operations.correct_past_fix import learners_bookmarks, move
from zeeguu.core.bookmark_operations.update_bookmark import BookmarkValidationError
from zeeguu.core.model.validation_log import ValidationLog
from zeeguu.core.tokenization.word_position_finder import validate_single_occurrence

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
        shown = f"{fix.new_meaning.origin.content} = {fix.new_meaning.translation.content} -> {card}"
        bookmarks = learners_bookmarks(fix)
        place = validate_single_occurrence(word, fix.context, fix.new_meaning.origin.language)
        if not bookmarks or not place["valid"]:
            why = "no bookmark left in the sentence" if not bookmarks else f"'{word}' {place['error_type']}"
            print(f"SKIP  log {fix.id}: {shown} ({why})")
            skipped += 1
            continue
        for bookmark in bookmarks:
            user_word = bookmark.user_word
            print(f"{'MOVE' if args.apply else 'WOULD'}  log {fix.id}: bookmark {bookmark.id} of user "
                  f"{user_word.user_id}: {shown}"
                  f"{'' if len(user_word.bookmarks()) == 1 else ' (the word keeps its other sentences)'}")
            if not args.apply:
                continue
            savepoint = session.begin_nested()
            try:
                move(session, bookmark, fix, word, translation, card)
                savepoint.commit()
                session.commit()
                moved += 1
            except BookmarkValidationError as e:
                savepoint.rollback()
                print(f"SKIP  log {fix.id}: {e}")
                skipped += 1

    print(f"\n{moved} moved, {skipped} skipped" if args.apply else f"\nDry run; {skipped} would be skipped")


if __name__ == "__main__":
    main()
