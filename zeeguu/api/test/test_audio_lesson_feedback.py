"""
Feedback after a daily audio lesson: /audio_lesson_feedback.

Pace, repetition and length are recorded per lesson and tune the next A0
lessons; a situation moves the daily lessons on (or back, with "stay").
"""

from zeeguu.api.test.fixtures import logged_in_client, LoggedInClient
from zeeguu.core.audio_lessons.lesson_tuning import LessonTuning, tuning_for
from zeeguu.core.model import User
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.audio_lesson_feedback import AudioLessonFeedback
from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.daily_audio_subscription import DailyAudioSubscription
from zeeguu.core.model.db import db
from zeeguu.core.model.user_preference import UserPreference


def _lesson_for(email, situation="grocery shopping", a0=True, minutes=None):
    user = User.find(email)
    lesson = DailyAudioLesson(
        user=user, created_by="test", duration_seconds=300,
        raw_suggestion=situation, canonical_suggestion=situation, lesson_type="situation",
    )
    lesson.next_situations = ["at the bakery", "asking the time", "taking the bus"]
    db.session.add(lesson)
    dialogue = AudioLessonDialogue(
        script="Man: Hej.", canonical_suggestion=situation, lesson_type="situation",
        language=user.learned_language, builds_on_history=a0,
    )
    if minutes:
        dialogue.tuning = {"pace": 0, "repetition": 0, "length": 0, "minutes": minutes}
    db.session.add(dialogue)
    db.session.add(
        DailyAudioLessonSegment(lesson, segment_type="dialogue_lesson", audio_lesson_dialogue=dialogue)
    )
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
    _say(logged_in_client, second, "length", "longer")

    user = User.find(logged_in_client.email)
    assert tuning_for(user, user.learned_language) == LessonTuning(0, 2, -1)


def test_too_short_asks_for_a_step_more_than_the_lesson_was(logged_in_client):
    first = _lesson_for(logged_in_client.email, minutes=10)
    second = _lesson_for(logged_in_client.email, minutes=10)

    # Two lessons written for 10 minutes, both too short: 15, not 20.
    assert _say(logged_in_client, first, "length", "longer").json["lesson_minutes"] == 15
    assert _say(logged_in_client, second, "length", "longer").json["lesson_minutes"] == 15
    # The next one, written for 15, still too short.
    third = _lesson_for(logged_in_client.email, minutes=15)
    assert _say(logged_in_client, third, "length", "longer").json["lesson_minutes"] == 20

    user = User.find(logged_in_client.email)
    assert UserPreference.get_audio_lesson_minutes(user) == 20


def test_changing_the_length_answer_moves_from_the_same_place(logged_in_client):
    lesson = _lesson_for(logged_in_client.email, minutes=10)
    _say(logged_in_client, lesson, "length", "longer")

    assert _say(logged_in_client, lesson, "length", "just_right").json["lesson_minutes"] == 10
    assert _say(logged_in_client, lesson, "length", "shorter").json["lesson_minutes"] == 5


def test_a_lesson_from_before_the_length_was_stored_moves_from_the_setting(logged_in_client):
    lesson = _lesson_for(logged_in_client.email)
    # The default 5-minute daily goal.
    assert _say(logged_in_client, lesson, "length", "longer").json["lesson_minutes"] == 10


def test_the_lesson_length_is_a_preference_the_learner_can_set(logged_in_client):
    logged_in_client.post("/save_user_preferences", data={"audio_lesson_minutes": "20"})
    assert logged_in_client.get("/user_preferences")["audio_lesson_minutes"] == "20"


def test_a_lesson_length_that_is_not_a_choice_is_refused(logged_in_client):
    response = logged_in_client.client.post(
        logged_in_client.append_session("/save_user_preferences"), data={"audio_lesson_minutes": "17"}
    )
    assert response.status_code == 400


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


def test_situation_lesson_count_is_the_current_run(logged_in_client):
    from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator

    def count(lesson_id):
        return DailyLessonGenerator._situation_lesson_count(DailyAudioLesson.query.get(lesson_id))

    _lesson_for(logged_in_client.email)
    _lesson_for(logged_in_client.email)
    _lesson_for(logged_in_client.email, "at the bakery")
    back = _lesson_for(logged_in_client.email)
    again = _lesson_for(logged_in_client.email)

    assert count(back) == 1 and count(again) == 2


def test_a_situation_answer_on_an_older_lesson_does_not_move_the_lessons(logged_in_client):
    sub_id = _subscribe(logged_in_client.email, "at the bakery")
    older = _lesson_for(logged_in_client.email)
    _lesson_for(logged_in_client.email, "at the bakery")

    assert _say(logged_in_client, older, "situation", "stay").status_code == 200
    assert DailyAudioSubscription.query.get(sub_id).raw_suggestion == "at the bakery"


def test_a_situation_answer_on_yesterdays_lesson_counts_while_nothing_moved(logged_in_client):
    """The learner finishes yesterday's lesson after today's was made."""
    sub_id = _subscribe(logged_in_client.email)
    yesterday = _lesson_for(logged_in_client.email)
    _lesson_for(logged_in_client.email)

    _say(logged_in_client, yesterday, "situation", "at the bakery")
    assert DailyAudioSubscription.query.get(sub_id).raw_suggestion == "at the bakery"


def test_only_a0_lessons_take_feedback(logged_in_client):
    lesson = _lesson_for(logged_in_client.email, a0=False)

    assert _say(logged_in_client, lesson, "length", "shorter").status_code == 400


def test_lessons_per_situation(logged_in_client):
    _lesson_for(logged_in_client.email)
    _lesson_for(logged_in_client.email)
    _lesson_for(logged_in_client.email, "at the bakery")

    response = logged_in_client.client.get(logged_in_client.append_session("/audio_lesson_situations"))

    assert sorted((r["raw_suggestion"], r["lessons"]) for r in response.json) == [
        ("at the bakery", 1), ("grocery shopping", 2),
    ]
