"""
Every learner report about a word lands in word_report, with the meaning and
the sentence it was about: exercise reports, the reader's meaning reports, and
"bad translation" when removing a word.
"""

from fixtures import (
    logged_in_client as client,
    add_one_bookmark,
    add_context_types,
    add_source_types,
)
from zeeguu.core.model import Bookmark, WordReport
from zeeguu.core.model.study_choice import StudyChoice


def _bookmark_id(client):
    add_context_types()
    add_source_types()
    return add_one_bookmark(client)


def test_exercise_report_keeps_the_word_and_the_sentence_shown(client):
    bookmark_id = _bookmark_id(client)

    result = client.post(
        "/report_exercise_issue",
        json=dict(
            bookmark_id=bookmark_id,
            exercise_source="Recognize",
            reason="wrong_translation",
            context_used="Er stellt sich hinter Präsident",
        ),
    )

    bookmark = Bookmark.find(bookmark_id)
    report = WordReport.query.get(result["report_id"])
    assert report.kind == WordReport.WRONG_TRANSLATION
    assert report.origin == WordReport.EXERCISE
    assert report.meaning == bookmark.user_word.meaning
    assert report.user_word == bookmark.user_word
    assert report.bookmark == bookmark
    assert report.sentence == "Er stellt sich hinter Präsident"
    assert report.exercise_source.source == "Recognize"


def test_context_wrong_is_a_bad_example(client):
    bookmark_id = _bookmark_id(client)

    result = client.post(
        "/report_exercise_issue",
        json=dict(bookmark_id=bookmark_id, exercise_source="Recognize", reason="context_wrong"),
    )

    bookmark = Bookmark.find(bookmark_id)
    report = WordReport.query.get(result["report_id"])
    assert report.kind == WordReport.BAD_EXAMPLE
    assert report.sentence == bookmark.get_context()


def test_the_same_exercise_is_reported_once(client):
    bookmark_id = _bookmark_id(client)
    report = dict(bookmark_id=bookmark_id, exercise_source="Recognize", reason="other")

    first = client.post("/report_exercise_issue", json=report)
    second = client.post("/report_exercise_issue", json=report)

    assert second["already_reported"]
    assert second["report_id"] == first["report_id"]


def test_a_reader_report_finds_the_learners_word(client):
    bookmark_id = _bookmark_id(client)

    result = client.post(
        "/report_meaning",
        json=dict(
            word="hinter",
            translation="behind",
            from_lang="de",
            to_lang="en",
            reason="wrong_meaning",
        ),
    )

    bookmark = Bookmark.find(bookmark_id)
    report = WordReport.query.get(result["report_id"])
    assert report.kind == WordReport.WRONG_TRANSLATION
    assert report.origin == WordReport.READER
    assert report.user_word == bookmark.user_word
    assert report.bookmark is None


def test_bad_translation_reports_the_word_and_skips_it(client):
    bookmark_id = _bookmark_id(client)

    client.post(f"/dont_use_in_exercises/{bookmark_id}", data=dict(reason="bad_translation"))

    bookmark = Bookmark.find(bookmark_id)
    report = WordReport.query.filter_by(bookmark_id=bookmark_id).one()
    assert report.kind == WordReport.WRONG_TRANSLATION
    assert report.origin == WordReport.WORD_LIST
    assert bookmark.user_word.study_choice == StudyChoice.SKIP
