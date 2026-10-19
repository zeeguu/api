#!/usr/bin/env python
"""
Reset meanings that are INVALID only because the validator moved a learner
to a bigger expression.

When the translation validator found a learner had selected too little ('ud'
in 'ud af') it moved them to the expression ('ud af' = 'out of') and marked
the old pair, 'ud' = 'out', INVALID, though it still holds for a learner who
met 'ud' in 'Han gik ud'. Since 2026-10-19 the audio word selector skips
INVALID meanings, so these lost their audio lessons for everyone, and the
validator no longer marks them. This resets the ones already marked, those
with no verdict that the pair itself is wrong, to NOT_VALIDATED: each
learner's word is judged in its own sentence when it is next scheduled, and
already scheduled ones by the nightly validate_scheduled_meanings.
On 2026-10-19: 871 meanings.

Usage:
    python -m tools.reset_meanings_invalidated_by_word_fixes           # report only
    python -m tools.reset_meanings_invalidated_by_word_fixes --apply   # change the data

--apply first writes the ids it resets to
$ZEEGUU_DATA_FOLDER/invalid_meaning_reset/reset-meanings-<timestamp>.json,
which is all an undo needs.
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from sqlalchemy import text

from zeeguu.core.model.meaning import Meaning

APPLY = "--apply" in sys.argv

# INVALID meanings whose fixes all changed the word, with no verdict that the
# pair itself is broken (an INVALID verdict, or a FIX keeping the same word)
ONLY_SELECTION_FIXED = text("""
    SELECT DISTINCT v.meaning_id
    FROM validation_log v
    JOIN meaning m ON m.id = v.meaning_id
    JOIN phrase po ON po.id = m.origin_id
    JOIN meaning nm ON nm.id = v.new_meaning_id
    JOIN phrase np ON np.id = nm.origin_id
    WHERE m.validated = 2
      AND v.action = 'FIXED' AND LOWER(TRIM(np.content)) <> LOWER(TRIM(po.content))
      AND NOT EXISTS (
          SELECT 1 FROM validation_log v2
          LEFT JOIN meaning nm2 ON nm2.id = v2.new_meaning_id
          LEFT JOIN phrase np2 ON np2.id = nm2.origin_id
          WHERE v2.meaning_id = v.meaning_id
            AND (v2.action = 'INVALID'
                 OR (v2.action = 'FIXED' AND LOWER(TRIM(np2.content)) = LOWER(TRIM(po.content)))))
""")
to_reset = [row[0] for row in db.session.execute(ONLY_SELECTION_FIXED)]

print(f"Mode: {'APPLY' if APPLY else 'REPORT ONLY'}")
print(f"{len(to_reset)} INVALID meanings whose only fixes changed the word")
for meaning_id in to_reset[:20]:
    meaning = db.session.get(Meaning, meaning_id)
    print(f"    meaning {meaning_id}: {meaning.origin.content} → {meaning.translation.content}")
if len(to_reset) > 20:
    print(f"    ... and {len(to_reset) - 20} more")

if not APPLY:
    if to_reset:
        print("Run again with --apply to reset them to NOT_VALIDATED.")
    sys.exit(0)

backup_dir = os.path.join(os.environ.get("ZEEGUU_DATA_FOLDER") or ".", "invalid_meaning_reset")
os.makedirs(backup_dir, exist_ok=True)
backup = os.path.join(backup_dir, f"reset-meanings-{datetime.now():%Y%m%d-%H%M%S}.json")
with open(backup, "w") as f:
    json.dump(to_reset, f)

for meaning_id in to_reset:
    db.session.get(Meaning, meaning_id).validated = Meaning.NOT_VALIDATED
db.session.commit()
print(f"Reset {len(to_reset)} meanings to NOT_VALIDATED (ids in {backup})")
