"""
Feedback after a daily audio lesson: /audio_lesson_feedback.

Pace, repetition and new words are recorded per lesson and tune the next A0
lessons; a situation moves the daily lessons on (or back, with "stay").
"""

from zeeguu.api.test.fixtures import logged_in_client, LoggedInClient
from zeeguu.core.audio_lessons.lesson_tuning import LessonTuning, tuning_for
from zeeguu.core.model import User
from zeeguu.core.model.audio_lesson_feedback import AudioLessonFeedback
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.daily_audio_subscription import DailyAudioSubscription
from zeeguu.core.model.db import db


def _lesson_for(email, situation="grocery shopping"):
    user = User.find(email)
    lesson = DailyAudioLesson(
        user=user, created_by="test", duration_seconds=300,
        raw_suggestion=situation, canonical_suggestion=situation, lesson_type="situation",
    )
    lesson.next_situations = ["at the bakery", "asking the time", "taking the bus"]
    db.session.add(lesson)
    db.session.commit()
    return lesson.id


def _subscribe(email, situation="grocery shopping", enabled=True):
    user = User.find(email)
    sub = DailyAudioSubscription(user, user.learned_language, "situation", situation)
    sub.enabled = enabled
    db.session.add(sub)
    db.session.commit()
    return sub.id


def _say(client, lesson_id, aspect, value):
    return client.client.post(
        client.append_session(f"/audio_lesson_feedback/{lesson_id}"),
        json={"aspect": aspect, "value": value},
    )


def test_feedback_is_recorded_and_can_be_changed(logged_in_client):
    lesson = _lesson_for(logged_in_client.email)

    assert _say(logged_in_client, lesson, "pace", "faster").status_code == 200
    response = _say(logged_in_client, lesson, "pace", "just_right")

    assert response.json["feedback"] == {"pace": "just_right"}
    assert AudioLessonFeedback.query.count() == 1


def test_feedback_tunes_the_next_lessons(logged_in_client):
    first = _lesson_for(logged_in_client.email)
    second = _lesson_for(logged_in_client.email)
    _say(logged_in_client, first, "repetition", "less")
    _say(logged_in_client, second, "repetition", "less")
    _say(logged_in_client, second, "new_words", "fewer")

    user = User.find(logged_in_client.email)
    assert tuning_for(user, user.learned_language) == LessonTuning(0, 2, -1)


def test_an_unknown_answer_is_refused(logged_in_client):
    lesson = _lesson_for(logged_in_client.email)

    assert _say(logged_in_client, lesson, "pace", "warp").status_code == 400
    assert _say(logged_in_client, lesson, "situation", "at the zoo").status_code == 400
    assert AudioLessonFeedback.query.count() == 0


def test_cannot_give_feedback_on_someone_elses_lesson(logged_in_client):
    other = LoggedInClient(logged_in_client.client, email="other@zeeguu.test")
    lesson = _lesson_for(other.email)

    assert _say(logged_in_client, lesson, "pace", "faster").status_code == 404


def test_choosing_a_situation_moves_the_daily_lessons_and_stay_moves_them_back(logged_in_client):
    sub_id = _subscribe(logged_in_client.email)
    lesson = _lesson_for(logged_in_client.email)

    _say(logged_in_client, lesson, "situation", "at the bakery")
    sub = DailyAudioSubscription.query.get(sub_id)
    assert sub.raw_suggestion == "at the bakery"

    _say(logged_in_client, lesson, "situation", "stay")
    sub = DailyAudioSubscription.query.get(sub_id)
    assert sub.raw_suggestion == "grocery shopping"


def test_choosing_a_situation_does_not_turn_lessons_back_on(logged_in_client):
    sub_id = _subscribe(logged_in_client.email, enabled=False)
    lesson = _lesson_for(logged_in_client.email)

    _say(logged_in_client, lesson, "situation", "at the bakery")
    sub = DailyAudioSubscription.query.get(sub_id)
    assert sub.raw_suggestion == "at the bakery" and sub.enabled is False


def test_situation_lesson_count(logged_in_client):
    from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator

    _lesson_for(logged_in_client.email, "at a café")
    _lesson_for(logged_in_client.email)
    third = _lesson_for(logged_in_client.email)

    assert DailyLessonGenerator._situation_lesson_count(DailyAudioLesson.query.get(third)) == 2
