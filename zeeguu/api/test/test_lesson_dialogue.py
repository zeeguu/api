"""Reading the dialogue of an audio lesson, line by line."""

import pytest

from fixtures import LoggedInClient, add_context_types, add_source_types
from fixtures import logged_in_client as client

from zeeguu.core.model import LessonDialogueText, User
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment
from zeeguu.core.model.db import db
from zeeguu.core.model.source_type import SourceType

SCRIPT = """Teacher: Listen to a conversation at a café. [1 seconds]
Man: Hallo! Was möchten Sie? [1 seconds]
Woman: Einen Kaffee, bitte. [1 seconds]
Man: Gern. [1 seconds]
Teacher: Now let's practice. [1 seconds]
Woman: Einen Kaffee, bitte. [3 seconds]
"""


@pytest.fixture(autouse=True)
def _types(app):
    with app.app_context():
        add_source_types()
        add_context_types()


# By email, not User: each request ends the session and detaches the objects.
def _dialogue(email, script=SCRIPT, dialogue_script=None):
    dialogue = AudioLessonDialogue(
        script=script, canonical_suggestion="cafe", lesson_type="situation",
        language=User.find(email).learned_language, title="Ordering coffee", difficulty_level="A0",
    )
    dialogue.dialogue_script = dialogue_script
    db.session.add(dialogue)
    db.session.commit()
    return dialogue


def _lesson(email, dialogue=None):
    lesson = DailyAudioLesson(user=User.find(email), created_by="test", duration_seconds=300)
    db.session.add(lesson)
    if dialogue:
        db.session.add(
            DailyAudioLessonSegment(lesson, segment_type="dialogue_lesson", audio_lesson_dialogue=dialogue)
        )
    db.session.commit()
    return lesson.id


def _read(client, lesson_id):
    return client.client.get(client.append_session(f"/lesson_dialogue/{lesson_id}"))


def _words(paragraph):
    return [token["text"] for sentence in paragraph for token in sentence]


def test_one_paragraph_per_line_and_who_says_it(client):
    me = client.email
    response = _read(client, _lesson(me, _dialogue(me)))

    assert response.status_code == 200
    result = response.json
    assert result["title"] == "Ordering coffee"
    assert result["speakers"] == ["Man", "Woman", "Man"]
    assert [_words(p) for p in result["tokenized_paragraphs"]] == [
        ["Hallo", "!", "Was", "möchten", "Sie", "?"],
        ["Einen", "Kaffee", ",", "bitte", "."],
        ["Gern", "."],
    ]
    text = LessonDialogueText.query.one()
    assert text.source_id == result["source_id"]
    assert text.source.source_type.type == SourceType.LESSON_DIALOGUE


def test_everyone_who_heard_the_dialogue_reads_the_same_text(client):
    me = client.email
    dialogue = _dialogue(me)
    other = LoggedInClient(client.client, email="other@zeeguu.test")

    mine = _read(client, _lesson(me, dialogue)).json["source_id"]
    theirs = _read(other, _lesson(other.email, dialogue)).json["source_id"]
    again = _read(client, _lesson(me, dialogue)).json["source_id"]

    assert mine == theirs == again
    assert LessonDialogueText.query.count() == 1


def test_tapped_word_becomes_a_bookmark_shown_again_on_reopening(client):
    """Through /translate_word, the way the reader sends a tap."""
    from zeeguu.core.model import Bookmark

    me = client.email
    lesson_id = _lesson(me, _dialogue(me))
    source_id = _read(client, lesson_id).json["source_id"]

    result = client.post(
        "/translate_word/de/en",
        json={
            "word": "Kaffee",
            "context": "Einen Kaffee, bitte.",
            "source_id": source_id,
            "w_sent_i": 0,
            "w_token_i": 1,
            "w_total_tokens": 1,
            "c_paragraph_i": 1,
            "c_sent_i": 2,
            "c_token_i": 0,
            "left_ellipsis": False,
            "right_ellipsis": False,
            "context_identifier": {"context_type": ContextType.LESSON_DIALOGUE},
            "translation_source": "reading",
        },
    )

    bookmark = Bookmark.find(result["bookmark_id"])
    assert bookmark.context.context_type.type == ContextType.LESSON_DIALOGUE
    assert bookmark.source_id == source_id
    assert [b["id"] for b in _read(client, lesson_id).json["past_bookmarks"]] == [bookmark.id]

    # In exercises the line stays: it is at the lesson's level (A0, as A1)
    from zeeguu.core.exercises.example_contexts import why_not_a_good_exercise_context

    assert why_not_a_good_exercise_context(Bookmark.find(result["bookmark_id"]), "A1") is None


def test_an_a0_lesson_reads_the_dialogue_it_stored(client):
    me = client.email
    stored = "Man: Guten Tag!\nWoman: Hallo!"

    result = _read(client, _lesson(me, _dialogue(me, dialogue_script=stored))).json

    assert [_words(p) for p in result["tokenized_paragraphs"]] == [["Guten", "Tag", "!"], ["Hallo", "!"]]


def test_a_line_that_would_split_into_two_paragraphs_is_refused():
    from zeeguu.core.audio_lessons.script_parser import DialogueLine
    from zeeguu.core.model.lesson_dialogue_text import NotOneParagraphPerLine

    lines = [DialogueLine("Man", "Hallo!\u2028Was möchten Sie?"), DialogueLine("Woman", "Kaffee.")]
    with pytest.raises(NotOneParagraphPerLine):
        LessonDialogueText.find_or_create(db.session, None, lines)


def test_not_for_someone_elses_lesson(client):
    other = LoggedInClient(client.client, email="other@zeeguu.test")

    assert _read(client, _lesson(other.email, _dialogue(client.email))).status_code == 404


def test_not_for_a_lesson_without_a_dialogue(client):
    me = client.email

    assert _read(client, _lesson(me)).status_code == 404
    assert _read(client, _lesson(me, _dialogue(me, script="Teacher: Hello."))).status_code == 404
