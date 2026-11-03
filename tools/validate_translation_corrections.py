#!/usr/bin/env python
"""
Runs the validator on readers' translation corrections (TranslationCorrection):
a learner's correction is shared with other readers only once the validator
calls it VALID here; a teacher's is shared at once and only audited here, its
verdict recorded but its status kept. Corrections the validator doesn't answer
are tried again the next night. Runs nightly from the ops crontab with
--apply; without it, only lists them.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.api.app import create_app_for_scripts
from zeeguu.core.model import db

app = create_app_for_scripts()
app.app_context().push()

from zeeguu.core.llm_services.translation_validator import TranslationValidator
from zeeguu.core.model.translation_correction import corrections_to_judge, judge

apply = "--apply" in sys.argv

corrections = corrections_to_judge()
print(f"{len(corrections)} translation corrections to judge")
validator = TranslationValidator() if apply and corrections else None

for correction in corrections:
    meaning = correction.meaning
    print(f"  {correction.id} [{correction.accepted_by or correction.status}] "
          f"{meaning.origin.content!r} -> {meaning.translation.content!r} "
          f"in {correction.context.get_content()[:70]!r}", flush=True)
    if apply:
        try:
            verdict = judge(db.session, correction, validator)
            print(f"    {verdict or 'no verdict'} -> {correction.status}", flush=True)
        except Exception as e:
            db.session.rollback()
            print(f"    failed: {e}", flush=True)

if not apply:
    print("(dry run; --apply to judge)")
