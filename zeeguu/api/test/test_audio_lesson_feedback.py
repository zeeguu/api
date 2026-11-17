"""
Feedback after a daily audio lesson: /audio_lesson_feedback.

Pace, repetition and length are recorded per lesson and tune the next dialogue
lessons of the same kind (A0, or the other levels); a situation moves the
daily lessons on (or back, with "stay").
"""

from zeeguu.api.test.fixtures import logged_in_client, LoggedInClient
from zeeguu.core.audio_lessons.lesson_tuning import LessonTuning, tuning_for
from zeeguu.core.model import Language, User
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.audio_lesson_feedback import AudioLessonFeedback
from zeeguu.core.model.daily_audio_lesson_segment import DailyAudioLessonSegment
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.daily_audio_subscription import DailyAudioSubscription
from zeeguu.core.model.db import db


def _lesson_for(email, situation="grocery shopping", a0=True):
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


def test_dialogue_lessons_above_a0_take_feedback_too(logged_in_client):
    lesson = _lesson_for(logged_in_client.email, a0=False)

    assert _say(logged_in_client, lesson, "length", "shorter").status_code == 200
    user = User.find(logged_in_client.email)
    assert tuning_for(user, user.learned_language, builds_on_history=False) == LessonTuning(length=1)


def test_a0_and_other_lessons_are_tuned_apart(logged_in_client):
    """A0 lessons are built on drilling: "less repetition" there says nothing
    about an A1 lesson, nor the other way round."""
    a0 = _lesson_for(logged_in_client.email)
    a1 = _lesson_for(logged_in_client.email, a0=False)
    _say(logged_in_client, a0, "repetition", "less")
    _say(logged_in_client, a1, "pace", "slower")

    user = User.find(logged_in_client.email)
    assert tuning_for(user, user.learned_language) == LessonTuning(repetition=1)
    assert tuning_for(user, user.learned_language, builds_on_history=False) == LessonTuning(pace=-1)


def test_word_lessons_take_no_feedback(logged_in_client):
    user = User.find(logged_in_client.email)
    lesson = DailyAudioLesson(user=user, created_by="test", duration_seconds=300)
    db.session.add(lesson)
    db.session.commit()

    assert _say(logged_in_client, lesson.id, "length", "shorter").status_code == 400
    assert AudioLessonFeedback.query.count() == 0


def test_lessons_per_situation(logged_in_client):
    _lesson_for(logged_in_client.email)
    _lesson_for(logged_in_client.email)
    _lesson_for(logged_in_client.email, "at the bakery")

    response = logged_in_client.client.get(logged_in_client.append_session("/audio_lesson_situations"))

    assert sorted((r["raw_suggestion"], r["lessons"]) for r in response.json) == [
        ("at the bakery", 1), ("grocery shopping", 2),
    ]


def _generator_writing(monkeypatch, written):
    """A DailyLessonGenerator whose script and audio calls are stubbed: each
    script written is recorded in `written` with the tuning it was asked for."""
    from types import SimpleNamespace

    from zeeguu.core.audio_lessons import daily_lesson_generator as module
    from zeeguu.core.audio_lessons.script_generator import GeneratedScript

    def write(**kwargs):
        written.append(kwargs["tuning"])
        return "A title", GeneratedScript("Man: Hej. [1 seconds]", "test-model", "v3")

    monkeypatch.setattr(module, "generate_dialogue_script", write)
    generator = module.DailyLessonGenerator()
    generator._voice_synthesizer = SimpleNamespace(
        generate_dialogue_audio=lambda **_: "/dev/null", get_audio_duration=lambda _: 60
    )
    return generator


def _dialogue_for(generator, user):
    return generator.generate_audio_lesson_dialogue(
        user, user.learned_language.code, "en", "B1", "at a café", "situation",
        is_general=True, voice_variety=None,
    )


def test_an_untuned_learner_above_a0_gets_a_shared_dialogue(logged_in_client, monkeypatch):
    user = User.find(logged_in_client.email)
    shared = AudioLessonDialogue(
        script="Man: Hej.", canonical_suggestion="at a café", lesson_type="situation",
        language=user.learned_language, teacher_language=Language.find_or_create("en"),
        difficulty_level="B1", is_general=True,
    )
    db.session.add(shared)
    db.session.commit()
    written = []

    assert _dialogue_for(_generator_writing(monkeypatch, written), user) == shared
    assert written == []


def test_a_tuned_learner_above_a0_gets_a_dialogue_of_their_own(logged_in_client, monkeypatch):
    _say(logged_in_client, _lesson_for(logged_in_client.email, a0=False), "pace", "slower")
    user = User.find(logged_in_client.email)
    shared = AudioLessonDialogue(
        script="Man: Hej.", canonical_suggestion="at a café", lesson_type="situation",
        language=user.learned_language, teacher_language=Language.find_or_create("en"),
        difficulty_level="B1", is_general=True,
    )
    db.session.add(shared)
    db.session.commit()
    written = []

    dialogue = _dialogue_for(_generator_writing(monkeypatch, written), user)

    assert dialogue != shared and written == [LessonTuning(pace=-1)]
    assert dialogue.is_general is False
    assert dialogue.tuning == {"pace": -1, "repetition": 0, "length": 0}
