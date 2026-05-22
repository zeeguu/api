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

  --fix-collisions
             Recovery mode for --copy: when winner.id collides with some other
             row's meaning_id, the winner's new path was already occupied by
             that other row's legacy file, so --copy skipped it. After --copy
             ran, those slots contain the WRONG audio (someone else's lesson)
             and the winner's audio is only at its legacy path. This mode
             force-overwrites those slots with the winner's legacy content.
             Safe because each other row also has its content at its OWN new
             path by this point.

Usage:
    python -m tools.migrate_audio_lesson_meaning_filenames                       # dry-run plan for --copy
    python -m tools.migrate_audio_lesson_meaning_filenames --copy --apply        # do the copy
    python -m tools.migrate_audio_lesson_meaning_filenames --fix-collisions      # dry-run the recovery
    python -m tools.migrate_audio_lesson_meaning_filenames --fix-collisions --apply
    python -m tools.migrate_audio_lesson_meaning_filenames --cleanup             # dry-run cleanup
    python -m tools.migrate_audio_lesson_meaning_filenames --cleanup --apply
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


def phase_fix_collisions(apply: bool):
    """Force-overwrite winners' new paths that --copy skipped due to collision."""
    groups = defaultdict(list)
    for row in AudioLessonMeaning.query.all():
        groups[(row.meaning_id, row.teacher_language_id)].append(row)

    planned = 0
    legacy_missing = 0

    for rows in groups.values():
        winner = max(rows, key=lambda r: r.id)
        lang_code = _lang_code(winner)
        old_path = os.path.join(LESSONS_DIR, f"meaning-{winner.meaning_id}-{lang_code}.mp3")
        new_path = os.path.join(LESSONS_DIR, f"meaning-{winner.id}-{lang_code}.mp3")

        if old_path == new_path:
            continue
        if not (os.path.exists(old_path) and os.path.exists(new_path)):
            if os.path.exists(new_path) and not os.path.exists(old_path):
                legacy_missing += 1
            continue

        # Only act when the file at new_path is NOT a byte-identical copy of old_path
        # (i.e. --copy didn't fill it; some other row's legacy file occupies it).
        try:
            same_size = os.path.getsize(old_path) == os.path.getsize(new_path)
        except OSError:
            same_size = False
        if same_size:
            with open(old_path, "rb") as a, open(new_path, "rb") as b:
                if a.read() == b.read():
                    continue  # already correct content

        planned += 1
        if apply:
            shutil.copy2(old_path, new_path)
        else:
            print(f"FORCE-COPY {old_path} -> {new_path}")

    print(f"\nFix-collisions phase: planned={planned}, winners_missing_legacy={legacy_missing}")
    if not apply:
        print("Dry run — re-run with --apply to overwrite.")


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
    parser.add_argument("--fix-collisions", action="store_true", dest="fix_collisions",
                        help="Overwrite new-path slots that --copy skipped because another row's legacy file already occupied them.")
    parser.add_argument("--cleanup", action="store_true", help="Delete leftover legacy files (run AFTER the new code is deployed).")
    parser.add_argument("--apply", action="store_true", help="Actually perform the file operations. Without this flag, only prints the plan.")
    args = parser.parse_args()

    modes = [args.copy, args.cleanup, args.fix_collisions]
    if sum(bool(m) for m in modes) > 1:
        sys.exit("Pass only one of --copy / --fix-collisions / --cleanup.")
    if not any(modes):
        print("No phase selected; showing --copy dry-run.\n")
        phase_copy(apply=False)
        sys.exit(0)

    if args.copy:
        phase_copy(apply=args.apply)
    elif args.fix_collisions:
        phase_fix_collisions(apply=args.apply)
    else:
        phase_cleanup(apply=args.apply)
