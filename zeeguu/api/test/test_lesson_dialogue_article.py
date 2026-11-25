"""Reading the dialogue of an audio lesson in the reader."""

from zeeguu.api.test.fixtures import logged_in_client, LoggedInClient
from zeeguu.core.model import ArticleDialogue, User
from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment
from zeeguu.core.model.db import db

SCRIPT = """Teacher: Listen to a conversation at a café. [1 seconds]
Man: Hej! Hvad skal du have? [1 seconds]
Woman: En kaffe, tak. [1 seconds]
Man: Værsgo. [1 seconds]
Teacher: Now let's practice. [1 seconds]
Woman: En kaffe, tak. [3 seconds]
"""


# By email, not User: each request ends the session and detaches the objects.
def _dialogue(email, script=SCRIPT, level="A0"):
    user = User.find(email)
    dialogue = AudioLessonDialogue(
        script=script, canonical_suggestion="cafe", lesson_type="situation",
        language=user.learned_language, title="Ordering coffee", difficulty_level=level,
    )
    db.session.add(dialogue)
    db.session.commit()
    return dialogue


def _lesson(email, dialogue=None):
    user = User.find(email)
    lesson = DailyAudioLesson(user=user, created_by="test", duration_seconds=300)
    db.session.add(lesson)
    if dialogue:
        db.session.add(
            DailyAudioLessonSegment(lesson, segment_type="dialogue_lesson", audio_lesson_dialogue=dialogue)
        )
    db.session.commit()
    return lesson.id


def _ask(client, lesson_id):
    return client.response_from_post(f"/lesson_dialogue_article/{lesson_id}")


def test_the_dialogue_becomes_an_article_with_a_fragment_per_line(logged_in_client):
    me = logged_in_client.email
    language_id = User.find(me).learned_language.id
    lesson_id = _lesson(me, _dialogue(me))

    response = _ask(logged_in_client, lesson_id)

    assert response.status_code == 200
    article_id = response.json["article_id"]
    fragments = ArticleFragment.get_all_article_fragments_in_order(article_id)
    assert [f.text.content for f in fragments] == ["Hej! Hvad skal du have?", "En kaffe, tak.", "Værsgo."]
    row = ArticleDialogue.find(article_id)
    assert row.speakers == ["Man", "Woman", "Man"]
    assert row.article.cefr_level == "A1"  # no A0 for texts
    assert row.article.language_id == language_id


def test_the_reader_gets_the_speakers(logged_in_client):
    me = logged_in_client.email
    article_id = _ask(logged_in_client, _lesson(me, _dialogue(me))).json["article_id"]

    info = logged_in_client.get(f"/user_article?article_id={article_id}")

    assert info["dialogue"]["speakers"] == ["Man", "Woman", "Man"]
    # The title is the lesson's, in the learner's own language: nothing to tap.
    assert info["title"] == "Ordering coffee"
    assert info["tokenized_title_new"]["tokens"] == []


def test_everyone_who_heard_the_dialogue_reads_the_same_article(logged_in_client):
    me = logged_in_client.email
    dialogue = _dialogue(me)
    other = LoggedInClient(logged_in_client.client, email="other@zeeguu.test")

    mine = _ask(logged_in_client, _lesson(me, dialogue)).json["article_id"]
    theirs = _ask(other, _lesson(other.email, dialogue)).json["article_id"]
    again = _ask(logged_in_client, _lesson(me, dialogue)).json["article_id"]

    assert mine == theirs == again
    assert ArticleDialogue.query.count() == 1


def test_not_for_someone_elses_lesson(logged_in_client):
    me = logged_in_client.email
    other = LoggedInClient(logged_in_client.client, email="other@zeeguu.test")
    others_lesson = _lesson(other.email, _dialogue(me))

    assert _ask(logged_in_client, others_lesson).status_code == 404


def test_not_for_a_lesson_without_a_dialogue(logged_in_client):
    me = logged_in_client.email

    assert _ask(logged_in_client, _lesson(me)).status_code == 404
    assert _ask(logged_in_client, _lesson(me, _dialogue(me, script="Teacher: Hello."))).status_code == 404
