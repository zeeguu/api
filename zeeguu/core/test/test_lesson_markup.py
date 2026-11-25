"""
A0 lesson scripts written with markers (lesson_markup.py): the model writes
each thing once, with roles (Learner, Other), and code relabels the roles as
voices, adds the repetitions and pauses, and turns what the learner answered
into cards that later lessons review (lesson_review.py).
"""

import re
from collections import Counter
from datetime import datetime, timedelta

import pytest

from zeeguu.core.audio_lessons import lesson_review
from zeeguu.core.audio_lessons.lesson_markup import (
    Card,
    MarkupError,
    card_lines,
    cards,
    expand,
    review_lines,
    roles_to_voices,
    spoken,
    time_to_answer,
    voices_to_roles,
    with_review,
)
from zeeguu.core.audio_lessons.lesson_review import ReviewItem
from zeeguu.core.audio_lessons.lesson_tuning import LessonTuning, prompt_values
from zeeguu.core.audio_lessons.words_heard import HeardLesson

VALUES = prompt_values(LessonTuning(), 10)  # answer pause 5 s, repeat 3 s, normal speed twice
DIALOGUE = (("man", "Hej! Hvad skal det være?"), ("woman", "En kaffe, tak."))
LEARNER = "woman"
BUS = HeardLesson(
    "Buying a bus ticket", Counter({"billet": 3}),
    (("woman", "Hej."), ("man", "Hej. En billet, tak."), ("woman", "Værsgo.")), "man",
)


def _expand(script, learner=LEARNER):
    return expand(roles_to_voices(script, learner), VALUES, DIALOGUE, learner)


# Roles and voices

def test_roles_become_the_voices_the_learner_has():
    script = "Teacher: Hi.\nLearner: Kaffe. [drill]\nOther: Hvad skal det være? [understand]"
    assert roles_to_voices(script, "woman").splitlines() == [
        "Teacher: Hi.", "Woman: Kaffe. [drill]", "Man: Hvad skal det være? [understand]",
    ]
    assert roles_to_voices(script, "man").splitlines()[1] == "Man: Kaffe. [drill]"


def test_a_bold_role_label_is_relabeled_too():
    assert roles_to_voices("**Learner:** Tak. [answer]", "woman") == "Woman: Tak. [answer]"


def test_the_dialogue_shown_to_the_model_has_roles():
    script = "Man: Hej! Hvad skal det være?\nWoman: En kaffe, tak."
    assert voices_to_roles(script, "woman") == "Other: Hej! Hvad skal det være?\nLearner: En kaffe, tak."


# Expansion

def test_drill_is_slow_once_then_at_normal_speed():
    assert _expand("Learner: Kaffe. [drill]").splitlines() == [
        "Woman: Kaffe. [slow] [3 seconds]",
        "Woman: Kaffe. [3 seconds]",
        "Woman: Kaffe. [3 seconds]",
    ]


def test_pace_and_repetition_come_from_the_tuning_not_the_model():
    faster = prompt_values(LessonTuning(pace=2, repetition=2), 10)
    expanded = expand(roles_to_voices("Learner: Kaffe. [drill]", LEARNER), faster, DIALOGUE, LEARNER)
    assert expanded.splitlines() == ["Woman: Kaffe. [slow] [2 seconds]", "Woman: Kaffe. [2 seconds]"]


def test_a_question_is_the_teacher_line_before_an_answer():
    lines = _expand("Teacher: How do you say coffee?\nLearner: En kaffe. [answer]").splitlines()
    # "En kaffe." is two words: 2 + 2.4 s to answer.
    assert lines == [
        "Teacher: How do you say coffee? [4 seconds]",
        "Woman: En kaffe. [3 seconds]",
        "Woman: En kaffe. [3 seconds]",
    ]


def test_in_an_exchange_the_learner_answers_the_other_person():
    script = (
        "Teacher: The shopkeeper tells you the price. Say okay, and ask for a ticket.\n"
        "Other: Den koster tolv kroner.\n"
        "Learner: Okay. En billet, tak. [answer]"
    )
    assert _expand(script).splitlines() == [
        "Teacher: The shopkeeper tells you the price. Say okay, and ask for a ticket. [1 seconds]",
        "Man: Den koster tolv kroner. [7 seconds]",  # the pause comes after the line answered
        "Woman: Okay. En billet, tak. [3 seconds]",
        "Woman: Okay. En billet, tak. [3 seconds]",
    ]


def test_a_second_answer_in_a_row_does_not_move_the_first_ones_pause():
    lines = _expand("Teacher: Say hello, then thanks.\nLearner: Hej. [answer]\nLearner: Tak. [answer]").splitlines()
    assert lines[0] == "Teacher: Say hello, then thanks. [3 seconds]"
    assert lines[1:3] == ["Woman: Hej. [3 seconds]"] * 2


def test_understand_and_dialogue_and_plain_lines():
    script = "Teacher: At the café.\n[dialogue]\nOther: Hvad skal det være? [understand]"
    assert _expand(script).splitlines() == [
        "Teacher: At the café. [1 seconds]",
        "Man: Hej! Hvad skal det være? [1 seconds]",
        "Woman: En kaffe, tak. [1 seconds]",
        "Man: Hvad skal det være? [slow] [1 seconds]",
        "Man: Hvad skal det være? [1 seconds]",
    ]


def test_no_marker_is_left_in_the_expanded_script():
    script = "Teacher: Hi.\n[dialogue]\nLearner: Kaffe. [drill]\nTeacher: Say it.\nLearner: Kaffe. [answer]"
    assert not re.search(r"\[(answer|drill|understand|dialogue)\]", _expand(script), re.IGNORECASE)


@pytest.mark.parametrize("script,problem", [
    ("Learner: Kaffe. [shout]", "unknown marker [shout]"),
    ("[review]", "not a marker that stands on its own line"),
    # No [ask] and no [cue]: what the learner answers is the line before [answer].
    ("Teacher: How do you say coffee? [ask]", "unknown marker [ask]"),
    ("Other: Den koster tolv kroner. [cue]", "unknown marker [cue]"),
])
def test_a_wrong_marker_is_refused_with_a_reason(script, problem):
    with pytest.raises(MarkupError, match=re.escape(problem)):
        _expand(script)


@pytest.mark.parametrize("marker", ["[plain]", "[no marker]", "[None]"])
def test_a_marker_meaning_no_marker_is_a_plain_line(marker):
    assert _expand(f"Learner: Tak. {marker}") == "Woman: Tak. [1 seconds]\n"


def test_a_title_line_is_kept():
    assert _expand("At the café\n\nTeacher: Hello.").startswith("At the café\n")


# Learned-language words inside a Teacher sentence

def test_a_chevron_span_is_said_by_the_teachers_learned_language_voice():
    assert spoken("Teacher", "The word for coffee is «kaffe». Say it.", 1) == [
        "Teacher: The word for coffee is [0 seconds]",
        "TeacherL2: kaffe. [0 seconds]",  # its punctuation comes with it
        "Teacher: Say it. [1 seconds]",
    ]


def test_a_teacher_line_ending_in_a_chevron_span_ends_with_the_pause():
    assert _expand("Teacher: Listen: «Hvad skal det være?»") == (
        "Teacher: Listen: [0 seconds]\nTeacherL2: Hvad skal det være? [1 seconds]\n"
    )


def test_chevrons_in_a_learned_language_line_are_just_dropped():
    assert _expand("Learner: «Tak». [answer]").splitlines()[0] == "Woman: Tak. [3 seconds]"


def test_the_language_check_does_not_read_chevron_spans_as_the_teachers_language():
    from zeeguu.core.audio_lessons.script_parser import parse_script

    assert parse_script("Teacher: The word for coffee is «kaffe».")[0][1] == "The word for coffee is."


# Time to answer

@pytest.mark.parametrize("answer,seconds", [
    ("Hej.", 3),                                  # 2 + 1.2
    ("En kaffe, tak.", 6),                        # 2 + 3.6
    ("Okay. En billet, tak.", 7),                 # 2 + 4.8
    ("Undskyld, hvad koster en billet?", 8),      # 2 + 6
    (" ".join(["ord"] * 30), 15),                 # capped
])
def test_the_time_to_answer_grows_with_the_answer(answer, seconds):
    assert time_to_answer(answer, VALUES) == seconds


def test_the_learners_pace_scales_the_time_to_answer():
    slowest = prompt_values(LessonTuning(pace=-2), 10)
    fastest = prompt_values(LessonTuning(pace=2), 10)
    assert time_to_answer("Undskyld, hvad koster en billet?", slowest) == 11  # 1.4 x 8
    assert time_to_answer("Hej.", fastest) == 2  # 0.6 x 3.2, at least 2


# Cards

MARKED = """Teacher: The word for ticket.
Learner: billet [drill]
Teacher: How do you say "ticket"?
Learner: billet [answer]
Other: Den koster tolv kroner. [understand]
Teacher: The shopkeeper tells you the price. Say okay, and ask for a ticket.
Other: Den koster tolv kroner.
Learner: Okay. En billet, tak. [answer]
Other: Værsgo.
Learner: Tak. [answer]
Teacher: Once more: how do you say "ticket"?
Learner: billet [answer]
[dialogue]"""


def _cards(marked=MARKED, learner=LEARNER):
    return cards(roles_to_voices(marked, learner), learner)


def test_cards_are_questions_and_exchanges_once_per_answer():
    assert _cards() == [
        Card(None, ("teacher", 'How do you say "ticket"?'), ("woman", "billet")),
        Card(
            "The shopkeeper tells you the price. Say okay, and ask for a ticket.",
            ("man", "Den koster tolv kroner."),
            ("woman", "Okay. En billet, tak."),
        ),
        # An exchange without a setup still works: hear the line, answer it.
        Card(None, ("man", "Værsgo."), ("woman", "Tak.")),
    ]
    assert [c.kind for c in _cards()] == ["question", "exchange", "exchange"]


def test_two_answers_to_one_question_make_one_card():
    marked = "Teacher: How do you say hello and thanks?\nLearner: Hej. [answer]\nLearner: Tak. [answer]"
    assert _cards(marked) == [Card(None, ("teacher", "How do you say hello and thanks?"), ("woman", "Hej."))]


def test_an_exchange_card_plays_the_setup_the_line_the_time_to_answer_and_the_answer():
    exchange = _cards()[1]
    assert card_lines(exchange, VALUES) == [
        "Teacher: The shopkeeper tells you the price. Say okay, and ask for a ticket. [1 seconds]",
        "Man: Den koster tolv kroner. [7 seconds]",
        "Woman: Okay. En billet, tak. [3 seconds]",
        "Woman: Okay. En billet, tak. [3 seconds]",
    ]


def test_a_question_card_asks_then_waits_then_answers():
    question = Card(None, ("teacher", "Ask what a ticket costs."), ("woman", "Undskyld, hvad koster en billet?"))
    assert card_lines(question, VALUES)[0] == "Teacher: Ask what a ticket costs. [8 seconds]"


# Review

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
    expanded = _expand("Teacher: Hi.\n[dialogue]\nLearner: Kaffe. [drill]\nTeacher: Listen again.\n[dialogue]")
    lines = with_review(expanded, review_lines([ReviewItem(BUS, None, None)], VALUES)).splitlines()
    assert lines.index("Teacher: Buying a bus ticket. [1 seconds]") < lines.index("Teacher: Listen again. [1 seconds]")
    assert lines[-2:] == ["Man: Hej! Hvad skal det være? [1 seconds]", "Woman: En kaffe, tak. [1 seconds]"]


NOW = datetime(2026, 11, 20, 12)


def _lesson(i, days_ago, reviewed=(), with_cards=False, learner="woman"):
    # Card ids: 10*i + their position, as AudioLessonCard rows would have them.
    lesson_cards = (
        tuple((10 * i + n, card) for n, card in enumerate(_cards(learner=learner)))
        if with_cards else ()
    )
    return HeardLesson(
        f"Lesson {i}", Counter(), ((learner, f"Hej {i}."), ("man" if learner == "woman" else "woman", f"Tak {i}.")),
        learner, i, NOW - timedelta(days=days_ago), reviewed, lesson_cards,
    )


def test_the_most_overdue_item_is_reviewed_first():
    # Overdue = days since last seen / interval (1 day, doubled per review).
    # Lesson 2: heard 6 days ago, never reviewed -> 6.
    # Lesson 1: heard 10 days ago, reviewed 6 days ago (by lesson 2) -> 6 / 2 = 3.
    # Lesson 3: heard 2 days ago, never reviewed -> 2.
    heard = [_lesson(1, 10), _lesson(2, 6, reviewed=((1, None),)), _lesson(3, 2)]
    assert [i.lesson.dialogue_id for i in lesson_review.due_order(heard, "woman", NOW)] == [2, 1, 3]


def test_each_card_is_spaced_on_its_own():
    # Card 10 of lesson 1 was reviewed 5 days ago (by lesson 2), card 11 never:
    # card 11 (9 days, interval 1) before card 10 (5 days, interval 2).
    heard = [_lesson(1, 9, with_cards=True), _lesson(2, 5, reviewed=((1, 10),))]
    order = [i.card_id for i in lesson_review.due_order(heard, "woman", NOW)]
    assert order.index(11) < order.index(10)


def test_a_lesson_with_cards_is_reviewed_by_cards_not_by_its_dialogue():
    items = lesson_review.items_of(_lesson(1, 3, with_cards=True), "woman")
    assert [i.card_id for i in items] == [10, 11, 12] and all(i.card for i in items)


def test_only_what_was_made_in_the_learners_current_voice_is_reviewed():
    """In many languages the learner's words depend on their gender: what they
    answered as a woman is not asked of them as a man."""
    as_woman = _lesson(1, 5, with_cards=True, learner="woman")
    as_man = _lesson(2, 4, learner="man")
    assert lesson_review.due_order([as_woman, as_man], "man", NOW) == [ReviewItem(as_man, None, None)]


def test_items_are_added_until_the_lesson_is_long_enough():
    heard = [_lesson(i, 30 - i) for i in range(1, 10)]
    # Each dialogue: title + 2 lines.
    assert len(lesson_review.choose(heard, 7, VALUES, "woman", NOW)) == 3


def test_a_lesson_long_enough_reviews_nothing():
    assert lesson_review.choose([_lesson(1, 3)], 0, VALUES, "woman", NOW) == []


def test_a_lesson_with_neither_cards_nor_a_dialogue_offers_nothing():
    empty = HeardLesson("Old", Counter(), (), None, 9, NOW - timedelta(days=50), ())
    assert lesson_review.due_order([empty], "woman", NOW) == []
