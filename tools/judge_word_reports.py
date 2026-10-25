#!/usr/bin/env python
"""
Runs the validator on the wrong_translation reports that have no verdict yet:
the ones from before reports were judged (26 Oct 2026), and the ones the
validator didn't answer. Lists them; pass --apply to judge them (LLM calls,
and a FIX or INVALID changes the meaning for every learner).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.model.word_report import WordReport
from zeeguu.core.word_reports import judge

apply = "--apply" in sys.argv

reports = WordReport.query.filter(
    WordReport.kind == WordReport.WRONG_TRANSLATION,
    WordReport.judged_at.is_(None),
).all()
print(f"{len(reports)} wrong_translation reports without a verdict")

for report in reports:
    meaning = report.meaning
    print(f"  {report.id} {meaning.origin.content!r} -> {meaning.translation.content!r} "
          f"in {(report.sentence or '')[:70]!r}", flush=True)
    if apply:
        try:
            judge(db.session, report)
            print(f"    {report.outcome or 'no verdict'}", flush=True)
        except Exception as e:
            db.session.rollback()
            print(f"    failed: {e}", flush=True)

if not apply:
    print("(dry run; --apply to judge)")
