"""
A0 lesson scripts written with markers (lesson_markup.py): the model writes
each thing once, code adds the repetitions and pauses, and tops a short
lesson up with rehearsal of earlier dialogues.
"""

from collections import Counter

import re

import pytest

from datetime import datetime, timedelta

from zeeguu.core.audio_lessons import lesson_review
from zeeguu.core.audio_lessons.lesson_markup import (
    MarkupError,
    expand,
    review_lines,
    with_review,
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
    assert expand("Woman: Kaffe. [drill]", VALUES, DIALOGUE).splitlines() == [
        "Woman: Kaffe. [slow] [3 seconds]",
        "Woman: Kaffe. [3 seconds]",
        "Woman: Kaffe. [3 seconds]",
    ]


def test_ask_waits_for_the_answer_and_the_answer_comes_twice():
    script = "Teacher: How do you say coffee? [ask]\nWoman: En kaffe. [answer]"
    assert expand(script, VALUES, DIALOGUE).splitlines() == [
        "Teacher: How do you say coffee? [5 seconds]",
        "Woman: En kaffe. [3 seconds]",
        "Woman: En kaffe. [3 seconds]",
    ]


def test_ask_on_its_own_line_belongs_to_the_question_before_it():
    """As the model wrote it in 4 of 17 eval lessons: without this, the learner
    got one second to answer."""
    script = "Teacher: How do you say coffee?\n[ask]\nWoman: En kaffe. [answer]"
    assert expand(script, VALUES, DIALOGUE).splitlines()[0] == "Teacher: How do you say coffee? [5 seconds]"


def test_no_marker_is_left_in_the_expanded_script():
    script = "Teacher: Hi.\n[ask]\n[dialogue]\nWoman: Kaffe. [drill]\nTeacher: Say it.\n[ask]\nWoman: Kaffe. [answer]"
    expanded = expand(script, VALUES, DIALOGUE)
    assert not re.search(r"\[(ask|answer|drill|understand|dialogue)\]", expanded, re.IGNORECASE)


def test_pace_and_repetition_come_from_the_tuning_not_the_model():
    faster = prompt_values(LessonTuning(pace=2, repetition=2), 10)
    assert expand("Woman: Kaffe. [drill]", faster, DIALOGUE).splitlines() == [
        "Woman: Kaffe. [slow] [2 seconds]",
        "Woman: Kaffe. [2 seconds]",
    ]


def test_understand_and_dialogue_and_plain_lines():
    script = "Teacher: At the café.\n[dialogue]\nMan: Hvad skal det være? [understand]"
    assert expand(script, VALUES, DIALOGUE).splitlines() == [
        "Teacher: At the café. [1 seconds]",
        "Man: Hej! Hvad skal det være? [1 seconds]",
        "Woman: En kaffe, tak. [1 seconds]",
        "Man: Hvad skal det være? [slow] [1 seconds]",
        "Man: Hvad skal det være? [1 seconds]",
    ]


def test_a_review_answers_only_before_the_learners_lines_then_plays_straight_through():
    lines = review_lines([BUS], VALUES)
    assert lines[:5] == [
        "",
        "Teacher: Buying a bus ticket. [1 seconds]",
        "Woman: Hej. [5 seconds]",          # the learner (man) answers next
        "Man: Hej. En billet, tak. [3 seconds]",
        "Woman: Værsgo. [1 seconds]",       # nothing to answer after it
    ]
    assert lines[-3:] == ["Woman: Hej. [1 seconds]", "Man: Hej. En billet, tak. [1 seconds]", "Woman: Værsgo. [1 seconds]"]


def test_the_review_goes_before_listen_again_and_the_closing_dialogue():
    expanded = expand("Teacher: Hi.\n[dialogue]\nWoman: Kaffe. [drill]\nTeacher: Listen again.\n[dialogue]", VALUES, DIALOGUE)
    lines = with_review(expanded, review_lines([BUS], VALUES)).splitlines()
    assert lines.index("Teacher: Buying a bus ticket. [1 seconds]") < lines.index("Teacher: Listen again. [1 seconds]")
    assert lines[-2:] == ["Man: Hej! Hvad skal det være? [1 seconds]", "Woman: En kaffe, tak. [1 seconds]"]


@pytest.mark.parametrize("script,problem", [
    ("Woman: Kaffe. [shout]", "unknown marker [shout]"),
    ("[review]", "not a marker that stands on its own line"),
    ("Woman: Hej.\n[ask]", "[ask] on its own line, not after a Teacher line"),
])
def test_a_wrong_marker_is_refused_with_a_reason(script, problem):
    with pytest.raises(MarkupError, match=re.escape(problem)):
        expand(script, VALUES, DIALOGUE)


@pytest.mark.parametrize("marker", ["[plain]", "[no marker]", "[None]"])
def test_a_marker_meaning_no_marker_is_a_plain_line(marker):
    assert expand(f"Woman: Tak. {marker}", VALUES, DIALOGUE) == "Woman: Tak. [1 seconds]\n"


def test_a_title_line_is_kept():
    assert expand("At the café\n\nTeacher: Hello.", VALUES, DIALOGUE).startswith("At the café\n")


NOW = datetime(2026, 11, 20, 12)


def _lesson(i, days_ago, reviewed=()):
    return HeardLesson(
        f"Lesson {i}", Counter(), (("woman", f"Hej {i}."), ("man", f"Tak {i}.")), "man",
        i, NOW - timedelta(days=days_ago), reviewed,
    )


def test_the_most_overdue_lesson_is_reviewed_first():
    # Overdue = days since last seen / interval (1 day, doubled per review).
    # Lesson 2: heard 6 days ago, never reviewed -> 6.
    # Lesson 1: heard 10 days ago, reviewed 6 days ago (by lesson 2) -> 6 / 2 = 3.
    # Lesson 3: heard 2 days ago, never reviewed -> 2.
    heard = [_lesson(1, 10), _lesson(2, 6, reviewed=(1,)), _lesson(3, 2)]
    assert [l.dialogue_id for l in lesson_review.due_order(heard, NOW)] == [2, 1, 3]


def test_reviews_are_added_until_the_lesson_is_long_enough():
    heard = [_lesson(i, 30 - i) for i in range(1, 10)]
    chosen = lesson_review.choose(heard, 12, lambda lesson: 5, NOW)
    assert len(chosen) == 3


def test_a_lesson_long_enough_reviews_nothing():
    assert lesson_review.choose([_lesson(1, 3)], 0, lambda lesson: 5, NOW) == []


def test_a_lesson_without_a_stored_dialogue_is_not_reviewed():
    no_dialogue = HeardLesson("Old", Counter(), (), None, 9, NOW - timedelta(days=50), ())
    assert lesson_review.due_order([no_dialogue, _lesson(1, 2)], NOW)[0].dialogue_id == 1
    assert len(lesson_review.due_order([no_dialogue], NOW)) == 0
