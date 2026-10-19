#!/usr/bin/env python
"""
Bring INVALID meanings in line with what the validator now does (2026-10-19).

1. A meaning marked INVALID only because the validator moved one learner to a
   bigger expression ('ud' in 'ud af' → 'ud af' = 'out of') is not a broken
   pair: 'ud' = 'out' still holds for others, and INVALID cost it its audio
   lessons for everyone. Those go back to NOT_VALIDATED, so each learner's
   word is judged in their own sentence when it is next scheduled. On
   2026-10-19: 871 meanings.
2. A broken pair (no correction possible, or a corrected translation for the
   same word) is taken out of study for every learner. The validator used to
   move or take out only the learner it was validating; it now does this
   itself (UserWord.take_meaning_out_of_study). On 2026-10-19: 1,437
   unlearned words on 526 meanings, 166 of them scheduled.

Usage:
    python -m tools.backfill_invalid_meanings           # report only
    python -m tools.backfill_invalid_meanings --apply   # change the data

--apply resets the meanings of (1) to NOT_VALIDATED, saving their ids first,
and for (2) sets fit_for_study = 0 and deletes the schedule of each unlearned
word on a broken pair, and logs one validation_log row per word with the reason
"[invalid meaning backfill]". Learned words are left alone.

Deleting a schedule loses its spaced-repetition state, which nothing else
keeps, so before changing anything the schedules are written to
$ZEEGUU_DATA_FOLDER/invalid_meaning_backfill/schedules-<timestamp>.jsonl, and
the reset meanings to reset-meanings-<timestamp>.json next to it.
To undo fit_for_study, every word this run changed has a validation_log row
with that reason.
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
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.model.validation_log import ValidationLog
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

APPLY = "--apply" in sys.argv
REASON = "[invalid meaning backfill] the pair is broken: no correction, or the translation was corrected"

# Meanings with a verdict that the pair is broken: an INVALID verdict (no
# correction), or a FIX whose corrected pair keeps the same word
BROKEN_PAIRS = text("""
    SELECT DISTINCT v.meaning_id
    FROM validation_log v
    JOIN meaning m ON m.id = v.meaning_id
    JOIN phrase po ON po.id = m.origin_id
    LEFT JOIN meaning nm ON nm.id = v.new_meaning_id
    LEFT JOIN phrase np ON np.id = nm.origin_id
    WHERE m.validated = 2
      AND (v.action = 'INVALID'
           OR (v.action = 'FIXED' AND LOWER(TRIM(np.content)) = LOWER(TRIM(po.content))))
""")
broken = [row[0] for row in db.session.execute(BROKEN_PAIRS)]

# INVALID only because of fixes that changed the word, with no verdict that
# the pair itself is broken
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

in_study = (
    db.session.query(UserWord)
    .filter(UserWord.meaning_id.in_(broken))
    .join(Meaning, UserWord.meaning_id == Meaning.id)
    .outerjoin(BasicSRSchedule, BasicSRSchedule.user_word_id == UserWord.id)
    .filter(Meaning.validated == Meaning.INVALID, UserWord.learned_time.is_(None))
    .filter((UserWord.fit_for_study == True) | (BasicSRSchedule.id != None))
    .all()
)
meaning_ids = sorted({w.meaning_id for w in in_study})
schedules = BasicSRSchedule.query.filter(
    BasicSRSchedule.user_word_id.in_([w.id for w in in_study])
).all() if in_study else []

print(f"Mode: {'APPLY' if APPLY else 'REPORT ONLY'}")
print(f"{len(to_reset)} INVALID meanings whose only fixes changed the word: back to NOT_VALIDATED")
print(
    f"{len(in_study)} unlearned words in study on {len(meaning_ids)} broken pairs, "
    f"of {len({w.user_id for w in in_study})} learners; {len(schedules)} scheduled"
)
for w in in_study[:20]:
    print(f"    user_word {w.id}: {w.meaning.origin.content} → {w.meaning.translation.content}")
if len(in_study) > 20:
    print(f"    ... and {len(in_study) - 20} more")

if not APPLY:
    if in_study or to_reset:
        print("Run again with --apply to change the data.")
    sys.exit(0)

backup_dir = os.path.join(os.environ.get("ZEEGUU_DATA_FOLDER") or ".", "invalid_meaning_backfill")
os.makedirs(backup_dir, exist_ok=True)
backup = os.path.join(backup_dir, f"schedules-{datetime.now():%Y%m%d-%H%M%S}.jsonl")
with open(backup, "w") as f:
    for s in schedules:
        row = {c.name: getattr(s, c.name) for c in BasicSRSchedule.__table__.columns}
        f.write(json.dumps(row, default=str) + "\n")
print(f"Schedules saved to {backup}")

reset_backup = backup.replace("schedules-", "reset-meanings-").replace(".jsonl", ".json")
with open(reset_backup, "w") as f:
    json.dump(to_reset, f)
for meaning_id in to_reset:
    db.session.get(Meaning, meaning_id).validated = Meaning.NOT_VALIDATED
db.session.commit()
print(f"Reset {len(to_reset)} meanings to NOT_VALIDATED (ids in {reset_backup})")

taken_out = []
for meaning_id in meaning_ids:
    meaning = db.session.get(Meaning, meaning_id)
    for w in UserWord.take_meaning_out_of_study(db.session, meaning_id):
        ValidationLog.log_invalid(db.session, meaning=meaning, user_word_id=w.id, reason=REASON)
        taken_out.append(w)
db.session.commit()
print(f"Took {len(taken_out)} words out of study on {len(meaning_ids)} meanings.")
