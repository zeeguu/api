"""
Tuning a learner's next A0 lessons from their feedback (lesson_tuning.py),
and the situations suggested for moving on (next_situations.py).
"""

from types import SimpleNamespace

import pytest

from zeeguu.core.audio_lessons.lesson_tuning import (
    LessonTuning,
    default_lesson_minutes,
    is_valid,
    lesson_minutes_after,
    prompt_values,
    tuning_from,
)
from zeeguu.core.audio_lessons.next_situations import parse_suggestions
from zeeguu.core.audio_lessons.script_generator import get_prompt_template


def _rows(*pairs):
    return [SimpleNamespace(aspect=a, value=v) for a, v in pairs]


def test_no_feedback_is_the_lesson_as_it_was():
    assert tuning_from([]) == LessonTuning(0, 0, 0)


def test_each_answer_moves_one_step_and_just_right_keeps_it():
    rows = _rows(("pace", "faster"), ("pace", "just_right"), ("repetition", "less"))
    assert tuning_from(rows) == LessonTuning(pace=1, repetition=1, length=0)


def test_levels_stay_within_two_at_every_step():
    # Clamped as it goes: after four "faster", one "slower" already slows down.
    rows = _rows(*[("pace", "faster")] * 4, ("pace", "slower"))
    assert tuning_from(rows).pace == 1


def test_situation_and_unknown_answers_do_not_tune():
    rows = _rows(("situation", "at the bakery"), ("pace", "warp"), ("mood", "happy"))
    assert tuning_from(rows) == LessonTuning()


def _lesson_prompt(values):
    common = dict(
        target_language="Danish", source_language="English", cefr_level="A0",
        suggestion="at a café", history="Nothing yet.", dialogue="Man: Hej.",
        learner_role="Man",
    )
    template = get_prompt_template("a0_dialogue_lesson--pimsleur_style_situation-v4.txt")
    return template.format(**common, **values)


def test_the_prompt_asks_for_recalls_as_tuned_and_no_pauses():
    """Pauses and repeats are added by code (test_lesson_markup.py); the
    prompt only says how often to recall."""
    prompt = _lesson_prompt(prompt_values(LessonTuning(pace=2, repetition=2), 10))
    assert "about 2 times over the lesson" in prompt
    # Words from earlier lessons come back less too ("tak", "hej").
    assert "come back once in the recalls" in prompt
    assert "seconds]" not in prompt


def test_the_prompt_leaves_the_review_to_code():
    prompt = _lesson_prompt(prompt_values(LessonTuning(), 15))
    assert "do not write one" in prompt and "[respond" not in prompt


def test_twenty_five_minutes_is_a_hard_cap():
    values = prompt_values(LessonTuning(), 25)
    assert (values["min_minutes"], values["max_minutes"]) == (22, 25)
    assert values["max_lines"] == 273


def test_length_and_repetition_are_separate():
    """A long lesson with little repetition: the length is the target,
    repetition is how the lines inside it are spent."""
    values = prompt_values(LessonTuning(repetition=2), 20)
    assert values["min_lines"] == 218 and values["recalls_to_say"] == 2


def test_lesson_length_defaults_to_the_daily_goal_but_not_under_ten():
    assert default_lesson_minutes(10) == 10
    assert default_lesson_minutes(20) == 20
    # The default 5-minute goal and the grandfathered 2 keep today's lessons.
    assert default_lesson_minutes(5) == 10
    assert default_lesson_minutes(2) == 10


def test_length_answered_before_it_was_a_setting_still_counts():
    # Two "longer" (level -2) on a 10-minute goal.
    assert default_lesson_minutes(10, length_level=-2) == 20


def test_too_short_and_too_long_move_the_length_a_step_with_no_limit_at_two():
    minutes = 10
    for _ in range(3):
        minutes = lesson_minutes_after(minutes, "longer")
    assert minutes == 25
    assert lesson_minutes_after(minutes, "shorter") == 20
    assert lesson_minutes_after(minutes, "just_right") == 25
    assert lesson_minutes_after(minutes, "longer") == 25


def test_the_length_stays_within_the_choices():
    assert lesson_minutes_after(25, "longer") == 25
    assert lesson_minutes_after(5, "shorter") == 5


@pytest.mark.parametrize("aspect,value,ok", [
    ("pace", "faster", True),
    ("repetition", "less", True),
    ("length", "shorter", True),
    ("new_words", "more", False),
    ("pace", "more", False),
    ("situation", "stay", True),
    ("situation", "at the bakery", True),
    ("situation", "at the zoo", False),
    ("volume", "louder", False),
])
def test_valid_answers(aspect, value, ok):
    lesson = SimpleNamespace(next_situations=["at the bakery", "asking the time"])
    assert is_valid(aspect, value, lesson) == ok


def test_suggestions_are_cleaned():
    answer = '```json\n["At the bakery.", "grocery shopping", "at the bakery", 3, "asking the time", "taking the bus"]\n```'
    assert parse_suggestions(answer, ["Grocery shopping"]) == [
        "at the bakery", "asking the time", "taking the bus",
    ]


def test_a_fence_on_one_line_is_stripped():
    assert parse_suggestions('```["at the bakery", "asking the time"]```') == [
        "at the bakery", "asking the time",
    ]


def test_an_answer_that_is_not_a_list_fails():
    with pytest.raises(Exception):
        parse_suggestions('{"situations": []}')
