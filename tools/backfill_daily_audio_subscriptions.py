#!/usr/bin/env python
"""
One-time backfill: create a DailyAudioSubscription for every (user, language)
that has a legacy `daily_audio_lesson_type_<lang>` UserPreference, copying the
type and verbatim suggestion. Idempotent — skips a (user, language) that already
has a subscription. Run once after the 26-05-29-b migration.

    source api/.venv/bin/activate && python -m tools.backfill_daily_audio_subscriptions [--dry-run]
"""

import argparse

parser = argparse.ArgumentParser(description="Backfill daily audio subscriptions from preferences")
parser.add_argument("--dry-run", action="store_true", help="Report without writing")
args = parser.parse_args()

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.model import User, Language, UserPreference, DailyAudioSubscription

TYPE_PREFIX = UserPreference.DAILY_AUDIO_LESSON_TYPE_PREFIX
VALID_TYPES = ("three_words_lesson", "topic", "situation")

type_prefs = UserPreference.query.filter(
    UserPreference.key.like(f"{TYPE_PREFIX}%")
).all()

created = skipped_exists = skipped_invalid = skipped_no_lang = 0

for pref in type_prefs:
    lesson_type = (pref.value or "").strip()
    if lesson_type not in VALID_TYPES:
        skipped_invalid += 1
        continue

    lang_code = pref.key[len(TYPE_PREFIX):]
    try:
        language = Language.find_or_create(lang_code)  # handles cn→zh-CN
    except Exception as e:
        print(f"  ! could not resolve language {lang_code!r} (user {pref.user_id}): {e}")
        skipped_no_lang += 1
        continue

    user = User.find_by_id(pref.user_id)
    if not user:
        continue

    if DailyAudioSubscription.find(user, language) is not None:
        skipped_exists += 1
        continue

    raw_suggestion = UserPreference.get(
        user, UserPreference.daily_audio_lesson_suggestion_key(lang_code)
    )
    raw_suggestion = (raw_suggestion or "").strip() or None

    print(f"  + user {user.id} [{language.code}] {lesson_type}: {raw_suggestion or '-'}")
    if not args.dry_run:
        db.session.add(DailyAudioSubscription(user, language, lesson_type, raw_suggestion))
    created += 1

if not args.dry_run:
    db.session.commit()

print("=" * 60)
print(f"created: {created}")
print(f"skipped (already had subscription): {skipped_exists}")
print(f"skipped (invalid type): {skipped_invalid}")
print(f"skipped (unresolved language): {skipped_no_lang}")
if args.dry_run:
    print("[DRY RUN] nothing written")
