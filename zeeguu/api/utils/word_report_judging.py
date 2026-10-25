from zeeguu.api.utils.background import run_in_background
from zeeguu.core.model.word_report import WordReport
from zeeguu.core.word_reports import judge_by_id


def judge_in_background(report):
    """A wrong_translation report runs the validator (word_reports.judge),
    which takes seconds: the learner doesn't wait for it."""
    if report.kind == WordReport.WRONG_TRANSLATION:
        run_in_background(judge_by_id, report.id)
