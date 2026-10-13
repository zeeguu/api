"""
Deleting a daily audio lesson.

The app can show a lesson from an earlier day (the paused one waiting to be
listened to). Deletion used to look only for a lesson created today, so on that
lesson it found nothing, answered 200, and the page reloaded with the same
lesson still there. The client now names the lesson it is showing.
"""

from datetime import datetime, timedelta

import pytest

from zeeguu.api.test.fixtures import logged_in_client, LoggedInClient
from zeeguu.api.utils.rate_limiter import get_limiter
from zeeguu.core.audio_lessons import daily_lesson_generator
from zeeguu.core.model import User
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment
from zeeguu.core.model.db import db


@pytest.fixture(autouse=True)
def _data_folder(tmp_path, monkeypatch):
    # Unset in tests; deletion removes the lesson's mp3 from under it.
    monkeypatch.setattr(daily_lesson_generator, "ZEEGUU_DATA_FOLDER", str(tmp_path))


def _lesson_for(email, days_ago=0, dialogue=None):
    user = User.find(email)
    lesson = DailyAudioLesson(user=user, created_by="test", duration_seconds=300)
    lesson.created_at = datetime.utcnow() - timedelta(days=days_ago)
    db.session.add(lesson)
    if dialogue:
        db.session.add(
            DailyAudioLessonSegment(
                lesson, segment_type="dialogue_lesson", audio_lesson_dialogue=dialogue
            )
        )
    db.session.commit()
    return lesson.id


def _delete(client, lesson_id):
    return client.client.delete(
        client.append_session(f"/delete_todays_lesson?lesson_id={lesson_id}")
    )


def test_deletes_a_lesson_from_an_earlier_day(logged_in_client):
    lesson_id = _lesson_for(logged_in_client.email, days_ago=3)

    assert _delete(logged_in_client, lesson_id).status_code == 200
    assert DailyAudioLesson.query.get(lesson_id) is None


def test_cannot_delete_someone_elses_lesson(logged_in_client):
    other = LoggedInClient(logged_in_client.client, email="other@zeeguu.test")
    lesson_id = _lesson_for(other.email)

    assert _delete(logged_in_client, lesson_id).status_code == 404
    assert DailyAudioLesson.query.get(lesson_id) is not None


def test_a_dialogue_shared_with_another_lesson_survives(logged_in_client):
    """Dialogues are a cache across users; deleting one would cut a piece out
    of the other learner's lesson."""
    me = User.find(logged_in_client.email)
    dialogue = AudioLessonDialogue(
        script="A: Hej", canonical_suggestion="cafe", lesson_type="topic",
        language=me.learned_language,
    )
    db.session.add(dialogue)
    db.session.commit()
    dialogue_id = dialogue.id

    other = LoggedInClient(logged_in_client.client, email="other@zeeguu.test")
    others_lesson = _lesson_for(other.email, dialogue=dialogue)
    my_lesson = _lesson_for(logged_in_client.email, dialogue=dialogue)

    assert _delete(logged_in_client, my_lesson).status_code == 200
    assert AudioLessonDialogue.query.get(dialogue_id) is not None
    assert len(DailyAudioLesson.query.get(others_lesson).segments) == 1


@pytest.fixture
def limiting_enabled():
    limiter = get_limiter()
    limiter.enabled = True
    yield limiter
    limiter.enabled = False
    limiter.reset()


def test_deletions_are_capped(logged_in_client, limiting_enabled):
    codes = [
        _delete(logged_in_client, _lesson_for(logged_in_client.email)).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]


def test_a_failed_delete_does_not_use_up_the_allowance(logged_in_client, limiting_enabled):
    for _ in range(5):
        assert _delete(logged_in_client, 999999).status_code == 404

    lesson_id = _lesson_for(logged_in_client.email)
    assert _delete(logged_in_client, lesson_id).status_code == 200


def test_a_second_session_shares_the_allowance(logged_in_client, limiting_enabled):
    """Logging in again must not hand out three more regenerations."""
    for _ in range(3):
        assert _delete(logged_in_client, _lesson_for(logged_in_client.email)).status_code == 200

    second = logged_in_client.client.post(
        f"/session/{logged_in_client.email}", data={"password": "test"}
    ).json["session"]
    assert second != logged_in_client.session
    logged_in_client.session = second

    assert _delete(logged_in_client, _lesson_for(logged_in_client.email)).status_code == 429
