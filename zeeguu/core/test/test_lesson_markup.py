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
    Card,
    MarkupError,
    card_lines,
    cards,
    time_to_answer,
    expand,
    review_lines,
    with_review,
)
from zeeguu.core.audio_lessons.lesson_review import ReviewItem
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


def test_no_marker_is_left_in_the_expanded_script():
    script = "Teacher: Hi.\n[dialogue]\nWoman: Kaffe. [drill]\nTeacher: Say it.\nWoman: Kaffe. [answer]"
    expanded = expand(script, VALUES, DIALOGUE)
    assert not re.search(r"\[(answer|drill|understand|cue|dialogue)\]", expanded, re.IGNORECASE)


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


MARKED = """Teacher: The word for ticket.
Man: billet [drill]
Teacher: How do you say "ticket"?
Man: billet [answer]
Woman: Den koster tolv kroner. [understand]
Teacher: Where is the bread?
Man: Hvor er brødet? [answer]
Woman: Den koster tolv kroner. [cue]
Teacher: Answer her: say okay, and ask for a ticket.
Man: Okay. En billet, tak. [answer]
Teacher: Once more: how do you say "ticket"?
Man: billet [answer]
[dialogue]"""


def test_cards_are_the_question_answer_pairs_once_per_answer_with_what_they_refer_to():
    assert cards(MARKED) == [
        Card(None, 'How do you say "ticket"?', ("man", "billet")),
        # The [understand] line before it is not what it refers to.
        Card(None, "Where is the bread?", ("man", "Hvor er brødet?")),
        Card(("woman", "Den koster tolv kroner."), "Answer her: say okay, and ask for a ticket.", ("man", "Okay. En billet, tak.")),
    ]


def test_a_card_gives_the_meaning_then_time_to_answer_then_the_answer():
    card = cards(MARKED)[2]
    lines = review_lines([ReviewItem(BUS, card, 7)], VALUES)
    assert lines == [
        "",
        "Woman: Den koster tolv kroner. [1 seconds]",
        "Teacher: Answer her: say okay, and ask for a ticket. [7 seconds]",  # a four-word answer
        "Man: Okay. En billet, tak. [3 seconds]",
        "Man: Okay. En billet, tak. [3 seconds]",
    ]


def test_a_lesson_without_cards_reviews_its_dialogue_answered_and_not_replayed():
    lines = review_lines([ReviewItem(BUS, None, None)], VALUES)
    assert lines == [
        "",
        "Teacher: Buying a bus ticket. [1 seconds]",
        "Woman: Hej. [7 seconds]",          # the learner (man) answers next, in four words
        "Man: Hej. En billet, tak. [3 seconds]",
        "Woman: Værsgo. [1 seconds]",       # nothing to answer after it
    ]


def test_the_review_goes_before_listen_again_and_the_closing_dialogue():
    expanded = expand("Teacher: Hi.\n[dialogue]\nWoman: Kaffe. [drill]\nTeacher: Listen again.\n[dialogue]", VALUES, DIALOGUE)
    lines = with_review(expanded, review_lines([ReviewItem(BUS, None, None)], VALUES)).splitlines()
    assert lines.index("Teacher: Buying a bus ticket. [1 seconds]") < lines.index("Teacher: Listen again. [1 seconds]")
    assert lines[-2:] == ["Man: Hej! Hvad skal det være? [1 seconds]", "Woman: En kaffe, tak. [1 seconds]"]


@pytest.mark.parametrize("script,problem", [
    ("Woman: Kaffe. [shout]", "unknown marker [shout]"),
    ("[review]", "not a marker that stands on its own line"),
    # No [ask]: the question is the Teacher line before an [answer].
    ("Teacher: How do you say coffee? [ask]", "unknown marker [ask]"),
    ("Teacher: How do you say coffee?\n[ask]", "not a marker that stands on its own line"),
    ("Man: Undskyld [ask]\nMan: Undskyld [answer]", "unknown marker [ask]"),
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


def _lesson(i, days_ago, reviewed=(), with_cards=False):
    # Card ids: 10*i + their position, as AudioLessonCard rows would have them.
    lesson_cards = tuple((10 * i + n, card) for n, card in enumerate(cards(MARKED))) if with_cards else ()
    return HeardLesson(
        f"Lesson {i}", Counter(), (("woman", f"Hej {i}."), ("man", f"Tak {i}.")), "man",
        i, NOW - timedelta(days=days_ago), reviewed, lesson_cards,
    )


def test_the_most_overdue_item_is_reviewed_first():
    # Overdue = days since last seen / interval (1 day, doubled per review).
    # Lesson 2: heard 6 days ago, never reviewed -> 6.
    # Lesson 1: heard 10 days ago, reviewed 6 days ago (by lesson 2) -> 6 / 2 = 3.
    # Lesson 3: heard 2 days ago, never reviewed -> 2.
    heard = [_lesson(1, 10), _lesson(2, 6, reviewed=((1, None),)), _lesson(3, 2)]
    assert [i.lesson.dialogue_id for i in lesson_review.due_order(heard, NOW)] == [2, 1, 3]


def test_each_card_is_spaced_on_its_own():
    # Card 10 of lesson 1 was reviewed 5 days ago (by lesson 2), card 11 never:
    # card 11 (9 days, interval 1) before card 10 (5 days, interval 2).
    heard = [_lesson(1, 9, with_cards=True), _lesson(2, 5, reviewed=((1, 10),))]
    order = [i.card_id for i in lesson_review.due_order(heard, NOW)]
    assert order.index(11) < order.index(10)


def test_a_lesson_with_cards_is_reviewed_by_cards_not_by_its_dialogue():
    items = lesson_review.items_of(_lesson(1, 3, with_cards=True))
    assert [i.card_id for i in items] == [10, 11, 12] and all(i.card for i in items)


def test_items_are_added_until_the_lesson_is_long_enough():
    heard = [_lesson(i, 30 - i) for i in range(1, 10)]
    # Each dialogue: title + 2 lines.
    assert len(lesson_review.choose(heard, 7, VALUES, NOW)) == 3


def test_a_lesson_long_enough_reviews_nothing():
    assert lesson_review.choose([_lesson(1, 3)], 0, VALUES, NOW) == []


def test_a_lesson_with_neither_cards_nor_a_dialogue_offers_nothing():
    empty = HeardLesson("Old", Counter(), (), None, 9, NOW - timedelta(days=50), ())
    assert lesson_review.due_order([empty], NOW) == []


def test_a_cue_is_said_once_like_a_plain_line():
    assert expand("Woman: Den koster tolv kroner. [cue]", VALUES, DIALOGUE) == "Woman: Den koster tolv kroner. [1 seconds]\n"


def test_the_teacher_line_before_an_answer_is_the_question():
    script = "Teacher: How do you say coffee?\nWoman: En kaffe. [answer]"
    # "En kaffe." is two words: 2 + 2.4 s.
    assert expand(script, VALUES, DIALOGUE).splitlines()[0] == "Teacher: How do you say coffee? [4 seconds]"




def test_two_answers_to_one_question_make_one_card():
    script = "Teacher: How do you say hello and thanks?\nMan: Hej. [answer]\nMan: Tak. [answer]"
    assert cards(script) == [Card(None, "How do you say hello and thanks?", ("man", "Hej."))]


def test_a_cue_only_counts_right_before_the_question():
    script = "Woman: Tolv kroner. [cue]\nTeacher: Listen.\nTeacher: Answer her.\nMan: Okay. [answer]"
    assert cards(script) == [Card(None, "Answer her.", ("man", "Okay."))]


@pytest.mark.parametrize("answer,seconds", [
    ("Hej.", 3),                                  # 2 + 1.2
    ("En kaffe, tak.", 6),                        # 2 + 3.6
    ("Okay. En billet, tak.", 7),                 # 2 + 4.8
    ("Undskyld, hvad koster en billet?", 8),      # 2 + 6
    (" ".join(["ord"] * 30), 15),                 # capped
])
def test_the_time_to_answer_grows_with_the_answer(answer, seconds):
    assert time_to_answer(answer, VALUES) == seconds


def test_a_longer_answer_gets_a_longer_pause_wherever_the_learner_answers():
    lesson = expand("Teacher: Ask what a ticket costs.\nMan: Undskyld, hvad koster en billet? [answer]", VALUES, DIALOGUE)
    assert lesson.splitlines()[0] == "Teacher: Ask what a ticket costs. [8 seconds]"
    card = Card(None, "Ask what a ticket costs.", ("man", "Undskyld, hvad koster en billet?"))
    assert card_lines(card, VALUES)[0] == "Teacher: Ask what a ticket costs. [8 seconds]"


def test_the_learners_pace_scales_the_time_to_answer():
    slowest = prompt_values(LessonTuning(pace=-2), 10)
    fastest = prompt_values(LessonTuning(pace=2), 10)
    assert time_to_answer("Undskyld, hvad koster en billet?", slowest) == 11  # 1.4 x 8
    assert time_to_answer("Hej.", fastest) == 2  # 0.6 x 3.2, at least 2
