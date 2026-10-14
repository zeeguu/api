#!/usr/bin/env python
"""
One-off: for words already in study whose exercise context is a fragment
the reader cut short, switch the context to one of the word's generated
example sentences.

From now on the exercise endpoint does this before a word's first exercise
(zeeguu/core/exercises/example_contexts.py). Words that were already
exercised are left to this script, run once, because afterwards a learner's
own choice of context must stick.

The fragment bookmark is kept; the exercise arrows still offer it.

Usage:
    python -m tools.backfill_example_contexts            # dry run: counts only
    python -m tools.backfill_example_contexts --apply [--limit N]
"""

import argparse

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.exercises.example_contexts import is_fragment, replace_fragment_with_example
from zeeguu.core.model import UserWord
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

db_session = db.session


def in_study_fragment_words(limit=None):
    query = (
        UserWord.query.join(BasicSRSchedule, BasicSRSchedule.user_word_id == UserWord.id)
        .filter(UserWord.fit_for_study == True)
        .order_by(UserWord.id)
    )
    found = []
    for user_word in query.yield_per(500):
        if user_word.preferred_bookmark and is_fragment(user_word.preferred_bookmark):
            found.append(user_word)
            if limit and len(found) >= limit:
                break
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="make the changes (default: dry run)")
    parser.add_argument("--limit", type=int, help="process at most N fragment words")
    args = parser.parse_args()

    words = in_study_fragment_words(args.limit)
    with_examples = [
        uw for uw in words if ExampleSentence.query.filter_by(meaning_id=uw.meaning_id).first()
    ]
    print(f"In-study words with a fragment context: {len(words)}")
    print(f"  ... of which have generated examples:  {len(with_examples)}")

    if not args.apply:
        print("Dry run. Pass --apply to switch them.")
        return

    swapped = failed = 0
    for i, user_word in enumerate(with_examples, 1):
        try:
            if replace_fragment_with_example(db_session, user_word):
                swapped += 1
        except Exception as e:
            failed += 1
            print(f"user_word {user_word.id}: {e}")
            db_session.rollback()
        if i % 100 == 0:
            print(f"{i}/{len(with_examples)}: {swapped} switched, {failed} failed")

    print(
        f"Done: {swapped} switched, {failed} failed, "
        f"{len(with_examples) - swapped - failed} had no example that anchors the word."
    )


if __name__ == "__main__":
    main()
