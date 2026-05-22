#!/usr/bin/env python
"""
Migrate meaning-lesson audio files from the legacy meaning_id-keyed naming
("meaning-{meaning_id}-{lang}.mp3") to the row-id-keyed naming
("meaning-{audio_lesson_meaning.id}-{lang}.mp3"), so distinct rows for the
same meaning (e.g. one deprecated, one regenerated) don't share a file.

Two phases, both idempotent and dry-run by default:

  --copy     For each (meaning_id, teacher_language_id) group, find the row
             with the highest id (the one whose script was last synthesized
             to disk under the legacy scheme) and copy
             meaning-{meaning_id}-{lang}.mp3 → meaning-{row_id}-{lang}.mp3.
             Older rows in the same group get no file; they'll be re-synthed
             lazily on next playback (existing fallback in
             daily_lesson_generator).

  --cleanup  After the new code is deployed, sweep meaning-*.mp3 files whose
             numeric component is NOT the id of any current audio_lesson_meaning
             row, but IS a meaning_id of some row. These are leftover legacy
             files. Conservative: skips anything that could double as a
             current-row file.

Usage:
    python -m tools.migrate_audio_lesson_meaning_filenames                    # dry-run plan for --copy
    python -m tools.migrate_audio_lesson_meaning_filenames --copy             # do the copy
    python -m tools.migrate_audio_lesson_meaning_filenames --cleanup          # dry-run plan for --cleanup
    python -m tools.migrate_audio_lesson_meaning_filenames --cleanup --apply  # do the cleanup
"""

import os
import re
import shutil
import sys
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.config import ZEEGUU_DATA_FOLDER
from zeeguu.core.model.audio_lesson_meaning import AudioLessonMeaning
from zeeguu.core.model.language import Language


LESSONS_DIR = os.path.join(ZEEGUU_DATA_FOLDER, "audio", "lessons")
FILENAME_RE = re.compile(r"^meaning-(\d+)-([a-z]{2})\.mp3$")


def _lang_code(row):
    return row.teacher_language.code if row.teacher_language else "en"


def phase_copy(apply: bool):
    """Copy legacy meaning_id-keyed files to row-id-keyed names."""
    # Pick the dominant (highest-id) row per (meaning_id, teacher_language_id).
    # That row's script is what was last synthesized to disk under the old scheme.
    groups = defaultdict(list)
    for row in AudioLessonMeaning.query.all():
        groups[(row.meaning_id, row.teacher_language_id)].append(row)

    planned = 0
    skipped_missing = 0
    skipped_existing = 0

    for rows in groups.values():
        winner = max(rows, key=lambda r: r.id)
        lang_code = _lang_code(winner)
        old_path = os.path.join(LESSONS_DIR, f"meaning-{winner.meaning_id}-{lang_code}.mp3")
        new_path = os.path.join(LESSONS_DIR, f"meaning-{winner.id}-{lang_code}.mp3")

        if old_path == new_path:
            # meaning_id == row.id; nothing to do
            continue

        if not os.path.exists(old_path):
            skipped_missing += 1
            continue

        if os.path.exists(new_path):
            skipped_existing += 1
            continue

        planned += 1
        if apply:
            shutil.copy2(old_path, new_path)
        else:
            print(f"COPY {old_path} -> {new_path}")

    print(f"\nCopy phase: planned={planned}, skipped_missing_legacy={skipped_missing}, skipped_already_new={skipped_existing}")
    if not apply:
        print("Dry run — re-run with --apply to copy files.")


def phase_cleanup(apply: bool):
    """Delete legacy meaning_id-keyed files left over after deploy."""
    current_row_ids = {r[0] for r in db.session.query(AudioLessonMeaning.id).all()}
    referenced_meaning_ids = {r[0] for r in db.session.query(AudioLessonMeaning.meaning_id).all()}

    if not os.path.isdir(LESSONS_DIR):
        print(f"Lessons dir not found: {LESSONS_DIR}")
        return

    planned = 0
    skipped_unrelated = 0
    skipped_in_use = 0

    for name in sorted(os.listdir(LESSONS_DIR)):
        m = FILENAME_RE.match(name)
        if not m:
            continue
        n = int(m.group(1))

        if n in current_row_ids:
            # This is a valid new-scheme file; leave it.
            skipped_in_use += 1
            continue

        if n not in referenced_meaning_ids:
            # Not a meaning_id we know about; probably orphaned, but conservative: skip.
            skipped_unrelated += 1
            continue

        path = os.path.join(LESSONS_DIR, name)
        planned += 1
        if apply:
            os.remove(path)
        else:
            print(f"DELETE {path}  (legacy meaning_id={n}; no row has this id)")

    print(f"\nCleanup phase: planned={planned}, kept_current_row_files={skipped_in_use}, kept_unrelated={skipped_unrelated}")
    if not apply:
        print("Dry run — re-run with --apply to delete files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--copy", action="store_true", help="Copy legacy files to row-id-keyed names.")
    parser.add_argument("--cleanup", action="store_true", help="Delete leftover legacy files (run AFTER the new code is deployed).")
    parser.add_argument("--apply", action="store_true", help="Actually perform the file operations. Without this flag, only prints the plan.")
    args = parser.parse_args()

    if args.copy and args.cleanup:
        sys.exit("Pass only one of --copy or --cleanup.")
    if not args.copy and not args.cleanup:
        # Default: show the copy-phase plan (the first thing you'd run).
        print("No phase selected; showing --copy dry-run.\n")
        phase_copy(apply=False)
        sys.exit(0)

    if args.copy:
        phase_copy(apply=args.apply)
    else:
        phase_cleanup(apply=args.apply)
