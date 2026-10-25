"""
A learner's "wrong translation" report runs the validator on the word in the
sentence they saw it in, even when the meaning was already judged VALID: a
VALID meaning is otherwise never looked at again. What the validator does
then is what it does anywhere else (a FIX moves the learner to the corrected
meaning and retires the old one for everyone), and its verdict goes on the
report.
"""
from datetime import datetime

from zeeguu.core.llm_services.validation_service import UserWordValidationService
from zeeguu.core.model import db
from zeeguu.core.model.validation_log import ValidationLog
from zeeguu.core.model.word_report import WordReport
from zeeguu.logging import log


def judge_by_id(report_id):
    """For run_in_background, which has its own session."""
    judge(db.session, WordReport.query.get(report_id))


def judge(session, report):
    """Judge a wrong_translation report. Commits."""
    # A reader report has no sentence of its own: the learner's word's
    bookmark = report.bookmark or (report.user_word and report.user_word.preferred_bookmark)
    user_word = bookmark.user_word if bookmark else None
    if user_word is None or user_word.meaning_id != report.meaning_id:
        return _record(session, report, "not_judged")

    logged_before = _last_log_id(user_word.id)
    kept = UserWordValidationService.validate_and_fix(
        session, user_word, bookmark=bookmark, recheck=True
    )
    verdict = (
        ValidationLog.query.filter(
            ValidationLog.user_word_id == user_word.id, ValidationLog.id > logged_before
        )
        .order_by(ValidationLog.id.desc())
        .first()
    )
    if verdict:
        return _record(session, report, verdict.action.value, verdict.id)
    if kept is None:
        return _record(session, report, "gave_up")
    log(f"[REPORT] No verdict for word_report {report.id}; judged again later")


def _last_log_id(user_word_id):
    last = (
        ValidationLog.query.filter(ValidationLog.user_word_id == user_word_id)
        .order_by(ValidationLog.id.desc())
        .first()
    )
    return last.id if last else 0


def _record(session, report, outcome, validation_log_id=None):
    report.outcome = outcome
    report.validation_log_id = validation_log_id
    report.judged_at = datetime.now()
    session.add(report)
    session.commit()
    log(f"[REPORT] word_report {report.id}: {outcome}")
