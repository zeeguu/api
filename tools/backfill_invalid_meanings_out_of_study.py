#!/usr/bin/env python
"""
Take words on INVALID meanings out of study, for every learner.

A meaning marked INVALID has a broken word/translation pair, whoever looked it
up. Until 2026-10-19 the translation validator moved or took out only the
learner it was validating; everyone else's word on the same pair stayed in
study. On that day that was 2,374 unlearned words of 948 learners on 915
INVALID meanings, 213 of them scheduled for exercises. The validator and the
audio lesson check now take such words out as they mark the meaning
(UserWord.take_meaning_out_of_study); this tool does it for what is already
there.

Usage:
    python -m tools.backfill_invalid_meanings_out_of_study           # report only
    python -m tools.backfill_invalid_meanings_out_of_study --apply   # change the data

--apply sets fit_for_study = 0 and deletes the schedule of each unlearned word
on an INVALID meaning, and logs one validation_log row per word with the reason
"[invalid meaning backfill]". Learned words are left alone.

Deleting a schedule loses its spaced-repetition state, which nothing else
keeps, so before changing anything the schedules are written to
$ZEEGUU_DATA_FOLDER/invalid_meaning_backfill/schedules-<timestamp>.jsonl.
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

from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.model.validation_log import ValidationLog
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

APPLY = "--apply" in sys.argv
REASON = "[invalid meaning backfill] the meaning is marked INVALID"

in_study = (
    db.session.query(UserWord)
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
print(
    f"{len(in_study)} unlearned words in study on {len(meaning_ids)} INVALID meanings, "
    f"of {len({w.user_id for w in in_study})} learners; {len(schedules)} scheduled"
)
for w in in_study[:20]:
    print(f"    user_word {w.id}: {w.meaning.origin.content} → {w.meaning.translation.content}")
if len(in_study) > 20:
    print(f"    ... and {len(in_study) - 20} more")

if not APPLY:
    if in_study:
        print("Run again with --apply to take them out of study.")
    sys.exit(0)

backup_dir = os.path.join(os.environ.get("ZEEGUU_DATA_FOLDER") or ".", "invalid_meaning_backfill")
os.makedirs(backup_dir, exist_ok=True)
backup = os.path.join(backup_dir, f"schedules-{datetime.now():%Y%m%d-%H%M%S}.jsonl")
with open(backup, "w") as f:
    for s in schedules:
        row = {c.name: getattr(s, c.name) for c in BasicSRSchedule.__table__.columns}
        f.write(json.dumps(row, default=str) + "\n")
print(f"Schedules saved to {backup}")

taken_out = []
for meaning_id in meaning_ids:
    meaning = db.session.get(Meaning, meaning_id)
    for w in UserWord.take_meaning_out_of_study(db.session, meaning_id):
        ValidationLog.log_invalid(db.session, meaning=meaning, user_word_id=w.id, reason=REASON)
        taken_out.append(w)
db.session.commit()
print(f"Took {len(taken_out)} words out of study on {len(meaning_ids)} meanings.")
