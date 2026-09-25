#!/usr/bin/env python
"""
Merge a duplicate account (SOURCE) into the account the person keeps (TARGET).

    python tools/merge_users.py SOURCE_ID TARGET_ID --dry-run
    python tools/merge_users.py SOURCE_ID TARGET_ID --commit [--take-email]

Moves words (merging the same meaning into one, keeping the richer row),
bookmarks, exercises, sessions, reading history, languages, classes, teacher
rights, preferences and audio lessons from SOURCE to TARGET, then deactivates
SOURCE: its email becomes merged-<src>-into-<tgt>@merged.zeeguu.invalid, its
password is randomised and its login sessions are deleted. Nothing is hard-
deleted except duplicates; see zeeguu/core/account_management/user_account_merge.py.

--take-email gives TARGET the SOURCE's email address (e.g. the student's new
school address), marked unverified. Without it TARGET keeps its own.

One of --dry-run / --commit is required. A dry run performs the whole merge in
a transaction, prints what it did, and rolls back.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model.db import db

app = create_app_for_scripts()
app.app_context().push()

from sqlalchemy import text

from zeeguu.core.model.user import User
from zeeguu.core.account_management.user_account_merge import merge_users, MergeError


def describe(user):
    def count(sql):
        return db.session.execute(text(sql), {"u": user.id}).scalar()

    languages = db.session.execute(
        text(
            "SELECT l.code FROM user_language ul JOIN language l ON l.id = ul.language_id "
            "WHERE ul.user_id = :u ORDER BY l.code"
        ),
        {"u": user.id},
    ).scalars()
    cohorts = db.session.execute(
        text(
            "SELECT c.name FROM user_cohort_map m JOIN cohort c ON c.id = m.cohort_id "
            "WHERE m.user_id = :u"
        ),
        {"u": user.id},
    ).scalars()
    return (
        f"  #{user.id} {user.name} <{user.email}>\n"
        f"    created {user.created_at}, last seen {user.last_seen}, "
        f"learning {user.learned_language.code if user.learned_language else '-'}\n"
        f"    words: {count('SELECT COUNT(*) FROM user_word WHERE user_id = :u')}, "
        f"bookmarks: {count('SELECT COUNT(*) FROM bookmark b JOIN user_word uw ON uw.id = b.user_word_id WHERE uw.user_id = :u')}, "
        f"languages: {', '.join(languages) or '-'}, "
        f"classes: {', '.join(cohorts) or '-'}, "
        f"teacher: {'yes' if count('SELECT COUNT(*) FROM teacher WHERE user_id = :u') else 'no'}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source_id", type=int, help="the duplicate, deactivated afterwards")
    parser.add_argument("target_id", type=int, help="the account that is kept")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    parser.add_argument("--take-email", action="store_true")
    args = parser.parse_args()

    source = User.find_by_id(args.source_id)
    target = User.find_by_id(args.target_id)
    if not source or not target:
        sys.exit(f"no such user: {args.source_id if not source else args.target_id}")

    print("SOURCE (will be deactivated):")
    print(describe(source))
    print("TARGET (kept):")
    print(describe(target))
    print("\nPer table:")

    try:
        merge_users(source, target, take_email=args.take_email)
    except MergeError as e:
        db.session.rollback()
        sys.exit(f"\nABORTED, nothing changed: {e}")

    if args.dry_run:
        db.session.rollback()
        print("\nDRY RUN: rolled back. Re-run with --commit to apply.")
        return

    db.session.commit()
    db.session.expire_all()
    print("\nCOMMITTED. After the merge:")
    print(describe(User.find_by_id(args.target_id)))
    print(describe(User.find_by_id(args.source_id)))


if __name__ == "__main__":
    main()
