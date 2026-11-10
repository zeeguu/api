#!/usr/bin/env python
"""
One-off: for learners' words whose exercise context is not a good exercise
sentence, switch the context to a generated example at or below the
learner's level.

Good means a whole sentence, at most 15 words, at or below the learner's
level (example_contexts.why_not_a_good_exercise_context). On 10 Nov 2026
only 24% of the contexts waiting to be practiced were. From now on the
exercise endpoint does this before a word's first exercise; this script
also covers words that were already exercised (an A2 learner shown B2
sentences looks up half of each, user 6885, 9 Nov 2026).

Words with no example at the learner's level yet keep their context; the
nightly prefetch_example_sentences_for_users writes those examples, so run
this after it. The original bookmark is kept; the exercise arrows still
offer it.

Usage:
    python -m tools.backfill_good_exercise_contexts                 # dry run, active learners
    python -m tools.backfill_good_exercise_contexts --user-id 6885  # dry run, one learner
    python -m tools.backfill_good_exercise_contexts --apply [--user-id N] [--days 30]
"""

import argparse
from collections import Counter
from datetime import datetime, timedelta

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.exercises.example_contexts import (
    learner_level,
    replace_context_with_example,
    usable_examples_query,
    why_not_a_good_exercise_context,
)
from zeeguu.core.model import Meaning, Phrase, User, UserWord

db_session = db.session


def learners(user_id, days):
    if user_id:
        return [User.find_by_id(user_id)]
    cutoff = datetime.now() - timedelta(days=days)
    return User.query.filter(User.last_seen > cutoff).order_by(User.id).all()


def words_in_study(user):
    """The learner's words in the language they learn now. All of them, not
    only scheduled ones: unscheduled words are the next to be introduced."""
    return (
        UserWord.query.join(Meaning, UserWord.meaning_id == Meaning.id)
        .join(Phrase, Meaning.origin_id == Phrase.id)
        .filter(UserWord.user_id == user.id)
        .filter(UserWord.fit_for_study == True)
        .filter(UserWord.preferred_bookmark_id != None)
        .filter(Phrase.language_id == user.learned_language_id)
        .order_by(UserWord.id)
        .all()
    )


def has_example_up_to(user_word, level):
    return usable_examples_query(user_word.meaning_id, level).first() is not None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="make the changes (default: dry run)")
    parser.add_argument("--user-id", type=int, help="only this learner")
    parser.add_argument("--days", type=int, default=30, help="learners seen in the last N days (default 30)")
    args = parser.parse_args()

    counts = Counter()
    for user in learners(args.user_id, args.days):
        words = words_in_study(user)
        if not words:
            continue
        level = learner_level(words[0])
        counts["learners"] += 1

        for user_word in words:
            user_word_id = user_word.id
            try:
                why = why_not_a_good_exercise_context(user_word.preferred_bookmark, level)
                if why is None:
                    counts["good"] += 1
                    continue
                counts[why] += 1
                counts["not good"] += 1
                if not args.apply:
                    # A read-only estimate: --apply also needs the word to be
                    # locatable in the example, and makes its bookmark.
                    if has_example_up_to(user_word, level):
                        counts["would switch"] += 1
                    continue
                if replace_context_with_example(db_session, user_word):
                    counts["switched"] += 1
            except Exception as e:
                counts["failed"] += 1
                # Roll back first: after a failed flush any ORM access raises.
                db_session.rollback()
                print(f"user_word {user_word_id}: {e}")

        if args.user_id or counts["learners"] % 50 == 0:
            print(f"after user {user.id}: {dict(counts)}")

    print(dict(counts))
    switched = counts["switched"] if args.apply else counts["would switch"]
    print(
        f"{counts['good']} contexts are good; {counts['not good']} are not; "
        f"{switched} {'switched' if args.apply else 'would switch'}; "
        f"the rest have no example at the learner's level yet."
    )
    if not args.apply:
        print("Dry run. Pass --apply to switch them.")


if __name__ == "__main__":
    main()
