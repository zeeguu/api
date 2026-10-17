#!/usr/bin/env python
"""
Recompute the reading evidence of learners' user_words (ADR 032): the
log-odds that a word is known from how it was read, and whether the practice
gate is closed for it. Meant to run nightly over the learners active in the
last --days; --days 100000 backfills everyone.

Prints every word whose gate opens or closes, so the refusals can be read
before the reading_gate feature reaches anyone but dev accounts.

    python -m tools.update_reading_evidence                 # active in the last 2 days
    python -m tools.update_reading_evidence --user 534 --dry-run --show-all
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.model import Bookmark, Language, Meaning, Phrase, User
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.word_scheduling.reading_evidence import (
    GATE_P_KNOWN,
    p_known,
    update_reading_evidence,
)


def active_user_ids(days):
    since = datetime.now() - timedelta(days=days)
    readers = db.session.query(UserReadingSession.user_id).filter(
        UserReadingSession.start_time >= since
    )
    translators = (
        db.session.query(UserWord.user_id)
        .join(Bookmark, Bookmark.user_word_id == UserWord.id)
        .filter(Bookmark.time >= since)
    )
    return sorted({uid for (uid,) in readers.union(translators) if uid})


def languages_with_words(user):
    language_ids = (
        db.session.query(Phrase.language_id)
        .join(Meaning, Meaning.origin_id == Phrase.id)
        .join(UserWord, UserWord.meaning_id == Meaning.id)
        .filter(UserWord.user_id == user.id)
        .distinct()
    )
    return Language.query.filter(Language.id.in_(language_ids)).all()


def describe(user_word, evidence):
    if evidence is None:
        return f"{user_word.meaning.origin.content!r}: no evidence"
    return (
        f"{user_word.meaning.origin.content!r} -> {user_word.meaning.translation.content!r}"
        f"  P={evidence.p_known:.2f}"
        f"  clean={evidence.clean_encounters} lookups={evidence.lookups}"
        f"  rank={user_word.meaning.origin.rank}"
    )


def main(user_ids, dry_run, show_all):
    closed = opened = 0
    for user_id in user_ids:
        user = User.find_by_id(user_id)
        for language in languages_with_words(user):
            changed = update_reading_evidence(db.session, user, language)
            for user_word, evidence in changed:
                if user_word.known_from_reading:
                    closed += 1
                    verb = "gated  "
                else:
                    opened += 1
                    verb = "ungated"
                print(f"user {user.id} {language.code} {verb} {describe(user_word, evidence)}")

            if show_all:
                still_gated = [
                    uw
                    for uw in UserWord.query.filter_by(user_id=user.id)
                    if uw.known_from_reading
                    and uw.meaning.origin.language_id == language.id
                ]
                print(
                    f"user {user.id} {language.code}: {len(still_gated)} words gated in total"
                )
                for uw in sorted(still_gated, key=lambda uw: -uw.reading_log_odds):
                    print(
                        f"    {uw.meaning.origin.content!r:20}"
                        f" P={p_known(uw.reading_log_odds):.2f} rank={uw.meaning.origin.rank}"
                    )

        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()

    print(
        f"{len(user_ids)} users; {closed} words gated, {opened} ungated"
        f" (gate at P(known) >= {GATE_P_KNOWN})" + (" -- DRY RUN" if dry_run else "")
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--days", type=int, default=2, help="learners active in the last N days")
    parser.add_argument("--user", type=int, help="only this user id")
    parser.add_argument("--dry-run", action="store_true", help="compute and print, write nothing")
    parser.add_argument("--show-all", action="store_true", help="list every gated word, not only changes")
    args = parser.parse_args()

    ids = [args.user] if args.user else active_user_ids(args.days)
    main(ids, args.dry_run, args.show_all)
