"""
A0 lesson scripts written with markers (lesson_markup.py): the model writes
each thing once, code adds the repetitions and pauses, and tops a short
lesson up with rehearsal of earlier dialogues.
"""

from collections import Counter

import re

import pytest

from zeeguu.core.audio_lessons.lesson_markup import (
    MarkupError,
    expand,
    expanded_line_count,
    top_up,
)
from zeeguu.core.audio_lessons.lesson_tuning import LessonTuning, prompt_values
from zeeguu.core.audio_lessons.words_heard import HeardLesson

VALUES = prompt_values(LessonTuning(), 10)  # answer 5 s, repeat 3 s, normal speed twice
DIALOGUE = (("man", "Hej! Hvad skal det være?"), ("woman", "En kaffe, tak."))
BUS = HeardLesson(
    "Buying a bus ticket", Counter({"billet": 3}),
    (("woman", "Hej."), ("man", "Hej. En billet, tak."), ("woman", "Værsgo.")), "man",
)
HEARD = [BUS]


def test_drill_is_slow_once_then_at_normal_speed():
    assert expand("Woman: Kaffe. [drill]", VALUES, DIALOGUE, HEARD).splitlines() == [
        "Woman: Kaffe. [slow] [3 seconds]",
        "Woman: Kaffe. [3 seconds]",
        "Woman: Kaffe. [3 seconds]",
    ]


def test_ask_waits_for_the_answer_and_the_answer_comes_twice():
    script = "Teacher: How do you say coffee? [ask]\nWoman: En kaffe. [answer]"
    assert expand(script, VALUES, DIALOGUE, HEARD).splitlines() == [
        "Teacher: How do you say coffee? [5 seconds]",
        "Woman: En kaffe. [3 seconds]",
        "Woman: En kaffe. [3 seconds]",
    ]


def test_pace_and_repetition_come_from_the_tuning_not_the_model():
    faster = prompt_values(LessonTuning(pace=2, repetition=2), 10)
    assert expand("Woman: Kaffe. [drill]", faster, DIALOGUE, HEARD).splitlines() == [
        "Woman: Kaffe. [slow] [2 seconds]",
        "Woman: Kaffe. [2 seconds]",
    ]


def test_understand_and_dialogue_and_plain_lines():
    script = "Teacher: At the café.\n[dialogue]\nMan: Hvad skal det være? [understand]"
    assert expand(script, VALUES, DIALOGUE, HEARD).splitlines() == [
        "Teacher: At the café. [1 seconds]",
        "Man: Hej! Hvad skal det være? [1 seconds]",
        "Woman: En kaffe, tak. [1 seconds]",
        "Man: Hvad skal det være? [slow] [1 seconds]",
        "Man: Hvad skal det være? [1 seconds]",
    ]


def test_respond_gives_time_to_answer_only_before_the_learners_lines():
    lines = expand("[respond 1]", VALUES, DIALOGUE, HEARD).splitlines()
    assert lines[:3] == [
        "Woman: Hej. [5 seconds]",          # the learner (man) answers next
        "Man: Hej. En billet, tak. [3 seconds]",
        "Woman: Værsgo. [1 seconds]",       # nothing to answer after it
    ]
    # Then straight through.
    assert lines[-3:] == ["Woman: Hej. [1 seconds]", "Man: Hej. En billet, tak. [1 seconds]", "Woman: Værsgo. [1 seconds]"]


@pytest.mark.parametrize("script,problem", [
    ("[respond 4]", "there is no lesson 4"),
    ("Woman: Kaffe. [shout]", "unknown marker [shout]"),
])
def test_a_wrong_marker_is_refused_with_a_reason(script, problem):
    with pytest.raises(MarkupError, match=re.escape(problem)):
        expand(script, VALUES, DIALOGUE, HEARD)


def test_a_title_line_is_kept():
    assert expand("At the café\n\nTeacher: Hello.", VALUES, DIALOGUE, HEARD).startswith("At the café\n")


def test_the_line_count_is_known_before_expanding():
    script = "Teacher: Hi.\nWoman: Kaffe. [drill]\n[dialogue]\n[respond 1]\nWoman: Tak. [answer]"
    lines = script.split("\n")
    expanded = expand(script, VALUES, DIALOGUE, HEARD)
    voice_lines = [l for l in expanded.splitlines() if ":" in l and not l.startswith("[")]
    assert expanded_line_count(lines, VALUES, DIALOGUE, HEARD) == len(voice_lines)


def _heard(n):
    return [
        HeardLesson(f"Lesson {i}", Counter(), (("woman", f"Hej {i}."), ("man", f"Tak {i}.")), "man")
        for i in range(1, n + 1)
    ]


def test_a_short_lesson_is_topped_up_before_the_closing_dialogue_newest_first():
    heard = _heard(40)
    marked = "Teacher: Hi.\n[dialogue]\nWoman: Kaffe. [drill]\nTeacher: Listen again.\n[dialogue]"
    topped = top_up(marked, VALUES, DIALOGUE, heard, 5)
    lines = topped.splitlines()
    assert lines[-2:] == ["Teacher: Listen again.", "[dialogue]"] and lines[1] == "[dialogue]"
    assert "Teacher: Lesson 40." in lines and "[respond 40]" in lines
    assert lines.index("[respond 40]") < lines.index("[respond 39]")
    assert expanded_line_count(lines, VALUES, DIALOGUE, heard) >= 5 * 60 / 5.5


def test_top_up_skips_lessons_already_rehearsed_and_stops_when_none_are_left():
    heard = _heard(2)
    topped = top_up("[respond 2]\n[dialogue]", VALUES, DIALOGUE, heard, 25)
    assert topped.count("[respond 2]") == 1 and "[respond 1]" in topped


def test_a_long_enough_lesson_is_left_alone():
    marked = "\n".join(["Teacher: Hi."] * 120) + "\n[dialogue]"
    assert top_up(marked, VALUES, DIALOGUE, _heard(3), 10) == marked
