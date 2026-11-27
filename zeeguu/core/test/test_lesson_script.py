"""
A0 lesson scripts written with markers (lesson_script): the model writes
each thing once, with roles (Learner, Other), and code relabels the roles as
voices, adds the repetitions and pauses, and turns what the learner answered
into challenges that later lessons review (lesson_review.py).
"""

import re
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from zeeguu.core.audio_lessons import lesson_review
from zeeguu.core.audio_lessons.lesson_script.challenges import Challenge, challenge_lines, challenges, dialogue_challenges, Utterance
from zeeguu.core.audio_lessons.lesson_script.expand import expand, expand_lines, MarkupError
from zeeguu.core.audio_lessons.lesson_script.review import review_lines, said_line_count, with_review
from zeeguu.core.audio_lessons.lesson_script.roles import roles_to_voices, voices_to_roles
from zeeguu.core.audio_lessons.lesson_script.spoken_line import spoken_lines, SpokenLine
from zeeguu.core.audio_lessons.lesson_script.time_to_answer import time_to_answer
from zeeguu.core.audio_lessons.lesson_tuning import LessonTuning, prompt_values
from zeeguu.core.audio_lessons.words_heard import HeardLesson

VALUES = prompt_values(LessonTuning(), 10)  # answer pause 5 s, repeat 3 s, normal speed twice
DIALOGUE = (("man", "Hej! Hvad skal det være?"), ("woman", "En kaffe, tak."))
LEARNER = "woman"


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
    ("[rehearse]", "not a marker that stands on its own line"),
    # No [ask] and no [cue]: what the learner answers is the line before [answer].
    ("Teacher: How do you say coffee? [ask]", "unknown marker [ask]"),
    ("Other: Den koster tolv kroner. [cue]", "unknown marker [cue]"),
])
def test_a_wrong_marker_is_refused_with_a_reason(script, problem):
    with pytest.raises(MarkupError, match=re.escape(problem)):
        _expand(script)


def test_a_pause_written_by_the_model_is_dropped_timing_is_codes():
    assert _expand("Teacher: Listen. [4 seconds]") == "Teacher: Listen. [1 seconds]\n"
    assert _expand("Teacher: How do you say coffee? [9 seconds]\nLearner: En kaffe. [answer]").splitlines()[0] == (
        "Teacher: How do you say coffee? [4 seconds]"
    )


@pytest.mark.parametrize("marker", ["[plain]", "[no marker]", "[None]"])
def test_a_marker_meaning_no_marker_is_a_plain_line(marker):
    assert _expand(f"Learner: Tak. {marker}") == "Woman: Tak. [1 seconds]\n"


# Learned-language words inside a Teacher sentence

def test_a_chevron_span_is_said_by_the_teachers_learned_language_voice():
    assert spoken_lines("teacher", "The word for coffee is «kaffe». Say it.", 1) == [
        SpokenLine("teacher", "The word for coffee is", 0, joined=True),
        SpokenLine("teacherl2", "kaffe.", 0, joined=True),  # its punctuation comes with it
        SpokenLine("teacher", "Say it.", 1),
    ]


def test_a_spoken_line_is_written_out_as_a_script_line():
    assert str(SpokenLine("teacher", "Say it.", 1)) == "Teacher: Say it. [1 seconds]"
    assert str(SpokenLine("woman", "Kaffe.", 3, slow=True)) == "Woman: Kaffe. [slow] [3 seconds]"
    assert str(SpokenLine("man", "Hej.", 0.5)) == "Man: Hej. [0.5 seconds]"


def test_a_teacher_line_ending_in_a_chevron_span_ends_with_the_pause():
    assert _expand("Teacher: Listen: «Hvad skal det være?»") == (
        "Teacher: Listen: [0 seconds]\nTeacherL2: Hvad skal det være? [1 seconds]\n"
    )


def test_chevrons_in_a_learned_language_line_are_just_dropped():
    assert _expand("Learner: «Tak». [answer]").splitlines()[0] == "Woman: Tak. [3 seconds]"


# Time to answer

@pytest.mark.parametrize("answer,seconds", [
    ("Hej.", 3),                                  # 2 + 1.2
    ("En kaffe, tak.", 6),                        # 2 + 3.6
    ("Okay. En billet, tak.", 7),                 # 2 + 4.8
    ("Undskyld, hvad koster en billet?", 8),      # 2 + 6
    (" ".join(["ord"] * 30), 12),                 # capped
])
def test_the_time_to_answer_grows_with_the_answer(answer, seconds):
    assert time_to_answer(answer, VALUES) == seconds


def test_the_learners_pace_scales_the_time_to_answer():
    slowest = prompt_values(LessonTuning(pace=-2), 10)
    fastest = prompt_values(LessonTuning(pace=2), 10)
    assert time_to_answer("Undskyld, hvad koster en billet?", slowest) == 11  # 1.4 x 8
    assert time_to_answer("Hej.", fastest) == 2  # 0.6 x 3.2, at least 2


# Challenges

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


def _challenges(marked=MARKED, learner=LEARNER):
    return challenges(roles_to_voices(marked, learner), learner)


def test_challenges_are_questions_and_exchanges_once_per_answer():
    assert _challenges() == [
        Challenge(None, Utterance("teacher", 'How do you say "ticket"?'), Utterance("woman", "billet")),
        Challenge(
            "The shopkeeper tells you the price. Say okay, and ask for a ticket.",
            Utterance("man", "Den koster tolv kroner."),
            Utterance("woman", "Okay. En billet, tak."),
        ),
        # An exchange without a setup still works: hear the line, answer it.
        Challenge(None, Utterance("man", "Værsgo."), Utterance("woman", "Tak.")),
    ]
    assert [c.kind for c in _challenges()] == ["question", "exchange", "exchange"]


def test_two_answers_to_one_question_make_one_challenge():
    marked = "Teacher: How do you say hello and thanks?\nLearner: Hej. [answer]\nLearner: Tak. [answer]"
    assert _challenges(marked) == [Challenge(None, Utterance("teacher", "How do you say hello and thanks?"), Utterance("woman", "Hej."))]


def test_an_exchange_challenge_plays_the_setup_the_line_the_time_to_answer_and_the_answer():
    exchange = _challenges()[1]
    assert challenge_lines(exchange, VALUES) == [
        SpokenLine("teacher", "The shopkeeper tells you the price. Say okay, and ask for a ticket.", 1),
        SpokenLine("man", "Den koster tolv kroner.", 7),
        SpokenLine("woman", "Okay. En billet, tak.", 3),
        SpokenLine("woman", "Okay. En billet, tak.", 3),
    ]


def test_a_question_challenge_asks_then_waits_then_answers():
    question = Challenge(None, Utterance("teacher", "Ask what a ticket costs."), Utterance("woman", "Undskyld, hvad koster en billet?"))
    assert challenge_lines(question, VALUES)[0] == SpokenLine("teacher", "Ask what a ticket costs.", 8)


# Review

ORDER_COFFEE = Challenge(
    "The waiter asks what you want. Ask for a coffee.",
    Utterance("man", "Hvad skal det være?"),
    Utterance("woman", "En kaffe, tak."),
)


def test_the_review_says_each_challenge_after_a_blank_line():
    assert review_lines([ORDER_COFFEE], VALUES) == [""] + challenge_lines(ORDER_COFFEE, VALUES)


def test_the_review_goes_before_listen_again_and_the_closing_dialogue():
    expanded = _expand("Teacher: Hi.\n[dialogue]\nLearner: Kaffe. [drill]\nTeacher: Listen again.\n[dialogue]")
    lines = with_review(expanded, review_lines([ORDER_COFFEE], VALUES)).splitlines()
    prompt = str(challenge_lines(ORDER_COFFEE, VALUES)[1])
    assert lines.index(prompt) < lines.index("Teacher: Listen again. [1 seconds]")
    assert lines[-2:] == ["Man: Hej! Hvad skal det være? [1 seconds]", "Woman: En kaffe, tak. [1 seconds]"]


# An old dialogue's challenges (tools/backfill_a0_challenges.py)

def test_each_learner_line_after_the_other_persons_line_is_an_exchange():
    dialogue = (("woman", "Hej."), ("man", "Hej. En billet, tak."), ("woman", "Værsgo."), ("man", "Tak."))
    assert dialogue_challenges(dialogue, "man") == [
        Challenge(None, Utterance("woman", "Hej."), Utterance("man", "Hej. En billet, tak.")),
        Challenge(None, Utterance("woman", "Værsgo."), Utterance("man", "Tak.")),
    ]


def test_an_old_dialogue_gives_no_challenge_for_a_first_line_or_a_repeated_answer():
    dialogue = (("man", "Hej."), ("woman", "Tak."), ("man", "Tak."), ("woman", "Hej."), ("man", "Hej."))
    assert [c.answer.text for c in dialogue_challenges(dialogue, "man")] == ["Tak.", "Hej."]
    assert dialogue_challenges((("man", "Hej."), ("woman", "Hej.")), "man") == []


# Spacing

NOW = datetime(2026, 11, 20, 12)


def _lesson(i, days_ago, reviewed=(), learner="woman"):
    # Challenge ids: 10*i + their position, as AudioChallenge rows would have them.
    # Answers differ per lesson: a review asks each answer once (see below).
    lesson_challenges = tuple(
        (10 * i + n, replace(challenge, answer=replace(challenge.answer, text=f"{challenge.answer.text} {i}")))
        for n, challenge in enumerate(_challenges(learner=learner))
    )
    return HeardLesson(f"Lesson {i}", Counter(), learner, i, NOW - timedelta(days=days_ago), reviewed, lesson_challenges)


def _ids(heard, learner="woman"):
    return [challenge_id for challenge_id, _ in lesson_review.due_challenges(heard, learner, NOW)]


def test_the_most_overdue_challenge_is_reviewed_first():
    # Overdue = days since last seen / interval (1 day, doubled per review).
    # Challenge 20 (lesson 2): heard 6 days ago, never reviewed -> 6.
    # Challenge 10 (lesson 1): heard 10 days ago, reviewed 6 days ago (by lesson 2) -> 6 / 2 = 3.
    # Challenge 30 (lesson 3): heard 2 days ago, never reviewed -> 2.
    heard = [_lesson(1, 10), _lesson(2, 6, reviewed=(10,)), _lesson(3, 2)]
    order = _ids(heard)
    assert order.index(20) < order.index(10) < order.index(30)


def test_each_challenge_is_spaced_on_its_own():
    # Challenge 10 of lesson 1 was reviewed 5 days ago (by lesson 2), challenge 11 never:
    # challenge 11 (9 days, interval 1) before challenge 10 (5 days, interval 2).
    order = _ids([_lesson(1, 9), _lesson(2, 5, reviewed=(10,))])
    assert order.index(11) < order.index(10)


def test_only_what_was_answered_in_the_learners_current_voice_is_reviewed():
    """In many languages the learner's words depend on their gender: what they
    answered as a woman is not asked of them as a man."""
    as_woman = _lesson(1, 5, learner="woman")
    as_man = _lesson(2, 4, learner="man")
    assert _ids([as_woman, as_man], "man") == [c for c, _ in as_man.challenges]


def test_challenges_are_added_until_the_lesson_is_long_enough():
    heard = [_lesson(1, 3)]
    first = len(challenge_lines(heard[0].challenges[0][1], VALUES))
    assert len(lesson_review.choose(heard, first, VALUES, "woman", NOW)) == 1
    assert len(lesson_review.choose(heard, first + 1, VALUES, "woman", NOW)) == 2


def test_a_lesson_long_enough_reviews_nothing():
    assert lesson_review.choose([_lesson(1, 3)], 0, VALUES, "woman", NOW) == []


def test_a_lesson_without_challenges_offers_nothing():
    empty = HeardLesson("Old", Counter(), None, 9, NOW - timedelta(days=50))
    assert lesson_review.due_challenges([empty], "woman", NOW) == []


def test_a_review_asks_each_answer_once_the_most_overdue():
    tak = lambda prompt: Challenge(None, Utterance("teacher", prompt), Utterance("woman", "Tak."))
    old = HeardLesson("Old", Counter(), "woman", 1, NOW - timedelta(days=9), (), ((10, tak("Say thanks."),),))
    new = HeardLesson("New", Counter(), "woman", 2, NOW - timedelta(days=2), (), ((20, tak("Thank the waiter."),),))
    assert _ids([old, new]) == [10]


# From the review of #978

@pytest.mark.parametrize("line", ["**Teacher:** How do you say coffee?", "Ask for a coffee.", "Here is your lesson:"])
def test_a_line_without_a_voice_label_is_refused_for_a_rewrite(line):
    with pytest.raises(MarkupError, match="without a voice label"):
        _expand(f"Teacher: The waiter asks what you want.\n{line}\nLearner: En kaffe. [answer]")


def test_a_marker_before_a_pause_the_model_wrote_is_still_read():
    assert _expand("Learner: Kaffe. [drill] [2 seconds]").splitlines()[0] == "Woman: Kaffe. [slow] [3 seconds]"


def test_the_review_goes_before_a_closing_sentence_with_chevrons_not_into_it():
    expanded = _expand(
        "Teacher: Hi.\n[dialogue]\nLearner: Kaffe. [drill]\n\n"
        "Teacher: Listen to the conversation at the «kaffebar» again.\n[dialogue]"
    )
    lines = with_review(expanded, review_lines([ORDER_COFFEE], VALUES)).splitlines()
    opening = lines.index("Teacher: Listen to the conversation at the [0 seconds]")
    assert lines[opening + 1:opening + 3] == ["TeacherL2: kaffebar [0 seconds]", "Teacher: again. [1 seconds]"]
    assert lines.index(str(challenge_lines(ORDER_COFFEE, VALUES)[1])) < opening


def test_a_sentence_with_chevrons_counts_as_one_line():
    script = roles_to_voices("Teacher: The word for coffee is «kaffe». Say it.\nTeacher: Good.", LEARNER)
    lines = expand_lines(script, VALUES, DIALOGUE, LEARNER)
    assert len(lines) == 4 and said_line_count(lines) == 2


@pytest.mark.parametrize("raw, title", [
    ("At the café\n\nTeacher: Hi.\n[dialogue]", "At the café"),
    ("**At the café**\nTeacher: Hi.\n[dialogue]", "At the café"),
    ("Woman: Kaffe. [drill]\nTeacher: Hi.", None),  # no title: the first line is a voice line
])
def test_the_title_is_the_first_line_when_it_is_not_a_voice_line(raw, title):
    from unittest.mock import patch

    from zeeguu.core.audio_lessons import script_generator

    a0 = {"values": VALUES, "dialogue": DIALOGUE, "learner": LEARNER, "heard": []}
    with patch.object(script_generator, "generate_script_in_languages", return_value=(raw, "model")):
        got, *_ = script_generator._write_dialogue_lesson(
            "prompt", a0, origin_language="da", translation_language="en", suggestion="café",
            max_tokens=100, short_lines=True,
        )
    assert (got.strip("*") if got else got) == title


def test_the_review_goes_before_listen_again_also_with_a_blank_line_before_the_dialogue():
    expanded = _expand("Teacher: Hi.\n[dialogue]\nLearner: Kaffe. [drill]\n\nTeacher: Now listen again.\n\n[dialogue]")
    lines = with_review(expanded, review_lines([ORDER_COFFEE], VALUES)).splitlines()
    assert lines.index(str(challenge_lines(ORDER_COFFEE, VALUES)[1])) < lines.index("Teacher: Now listen again. [1 seconds]")


def test_a_marker_on_a_teacher_line_is_refused():
    with pytest.raises(MarkupError, match="on a Teacher line"):
        _expand("Teacher: Say «tak». [drill]")


def test_a_challenge_answer_has_no_chevrons():
    marked = roles_to_voices("Teacher: How do you order a coffee?\nLearner: «En kaffe», tak. [answer]", LEARNER)
    assert challenges(marked, LEARNER)[0].answer == Utterance("woman", "En kaffe, tak.")


def test_an_answer_right_after_the_dialogue_makes_no_challenge():
    """In the lesson its prompt is the dialogue's last line, which a stored
    challenge does not have: the Teacher line before [dialogue] is not it."""
    marked = roles_to_voices("Teacher: How do you say thanks?\n[dialogue]\nLearner: Tak. [answer]", LEARNER)
    assert challenges(marked, LEARNER) == []


def test_the_language_check_reads_teacher_lines_without_their_chevron_spans():
    from zeeguu.core.audio_lessons.lesson_script.spoken_line import without_teacher_chevron_spans

    script = "Teacher: The word for coffee is «kaffe». Say it.\nWoman: «Kaffe»."
    assert without_teacher_chevron_spans(script) == "Teacher: The word for coffee is Say it.\nWoman: «Kaffe»."


def test_the_shared_parser_keeps_guillemets_in_teacher_lines():
    """Outside A0 «» are quotation marks (French, Russian...): the word in them is said."""
    from zeeguu.core.audio_lessons.script_parser import parse_script

    assert "«Bahnhof»" in parse_script("Teacher: Le mot «Bahnhof» veut dire gare.")[0][1]


# Prompt v5: [review], chevrons checked, the scene set first

V5 = (
    "Teacher: You are at the café.\n[dialogue]\nLearner: Kaffe. [drill]\n\n"
    "Teacher: Now some things from your earlier lessons.\n[review]\n\n"
    "Teacher: Listen again.\n[dialogue]"
)


def test_the_review_goes_where_the_model_put_review_after_its_introduction():
    lines = with_review(_expand(V5), review_lines([ORDER_COFFEE], VALUES)).splitlines()
    intro = lines.index("Teacher: Now some things from your earlier lessons. [1 seconds]")
    assert lines[intro + 1:intro + 3] == ["", "Teacher: The waiter asks what you want. Ask for a coffee. [1 seconds]"]
    assert "[review]" not in lines


def test_with_nothing_to_review_the_introduction_goes_too():
    text = with_review(_expand(V5), [])
    assert "earlier lessons" not in text and "[review]" not in text
    assert "Teacher: Listen again. [1 seconds]" in text


def test_a_chevron_span_must_be_a_learned_language_word_of_this_lesson_or_an_earlier_one():
    script = roles_to_voices(
        "Teacher: Hi.\n[dialogue]\nTeacher: You know «tak». The word for «very» is «mange».\nLearner: Mange tak. [drill]",
        LEARNER,
    )
    with pytest.raises(MarkupError, match="very is not one"):
        expand_lines(script, VALUES, DIALOGUE, LEARNER, known_words={"tak"})
    ok = script.replace("«very»", "very")
    assert expand_lines(ok, VALUES, DIALOGUE, LEARNER, known_words={"tak"})


def test_a_transliteration_in_chevrons_is_refused():
    script = roles_to_voices("Teacher: Hi.\n[dialogue]\nTeacher: You know «blagodarya».\nLearner: Благодаря. [drill]", LEARNER)
    with pytest.raises(MarkupError, match="blagodarya"):
        expand_lines(script, VALUES, (("man", "Благодаря."),), LEARNER, known_words=set())


def test_the_dialogue_is_not_played_before_the_teacher_sets_the_scene():
    with pytest.raises(MarkupError, match="set the scene first"):
        _expand("[dialogue]\nTeacher: Hi.\nLearner: Kaffe. [drill]")


# From the review of #988

def test_chevron_words_are_split_as_the_history_splits_them():
    script = roles_to_voices("Teacher: Hi.\n[dialogue]\nTeacher: You know «c'est».\nLearner: Oui. [drill]", LEARNER)
    assert expand_lines(script, VALUES, (("man", "Oui."),), LEARNER, known_words={"c'est"})


def test_with_nothing_to_review_an_introduction_a_blank_line_before_review_goes_too():
    script = V5.replace("earlier lessons.\n[review]", "earlier lessons.\n\n[review]")
    assert "earlier lessons" not in with_review(_expand(script), [])


def test_review_written_twice_is_refused():
    with pytest.raises(MarkupError, match="more than once"):
        _expand(V5.replace("[review]", "[review]\n[review]"))


def test_a_teacher_line_all_in_chevrons_sets_the_scene():
    assert _expand("Teacher: «Hej!»\n[dialogue]\nLearner: Kaffe. [drill]")


# Lessons above A0: shared between learners, written without a given
# dialogue or a learner's role (prompt dialogue_lesson--situation-v3)

def test_above_a0_a_long_answer_gets_more_time_than_a_short_one():
    script = (
        "Teacher: Ask the waiter for the bill.\n"
        "Man: Kan jeg få regningen? [answer]\n"
        "Teacher: Tell the waiter that you would like to pay by card, please.\n"
        "Man: Jeg vil gerne betale med kort, tak. [answer]"
    )
    lines = expand(script, VALUES).splitlines()
    # 4 words: 2 + 4.8 s; 7 words: 2 + 8.4 s.
    assert lines == [
        "Teacher: Ask the waiter for the bill. [7 seconds]",
        "Man: Kan jeg få regningen? [3 seconds]",
        "Man: Kan jeg få regningen? [3 seconds]",
        "Teacher: Tell the waiter that you would like to pay by card, please. [10 seconds]",
        "Man: Jeg vil gerne betale med kort, tak. [3 seconds]",
        "Man: Jeg vil gerne betale med kort, tak. [3 seconds]",
    ]


def test_above_a0_the_dialogue_is_written_out_and_said_once():
    script = "Teacher: At the café.\nWoman: Hej! Hvad skal det være?\nMan: En kaffe, tak."
    assert expand(script, VALUES).splitlines() == [
        "Teacher: At the café. [1 seconds]",
        "Woman: Hej! Hvad skal det være? [1 seconds]",
        "Man: En kaffe, tak. [1 seconds]",
    ]


def test_above_a0_a_dialogue_marker_is_refused():
    with pytest.raises(MarkupError, match=r"\[dialogue\]"):
        expand("Teacher: At the café.\n[dialogue]", VALUES)


def test_without_chevrons_guillemets_are_plain_quotation_marks():
    script = "Teacher: Dites «merci» au serveur.\nWoman: «Merci», dit-elle. [answer]"
    assert expand(script, VALUES, chevrons=False).splitlines() == [
        "Teacher: Dites «merci» au serveur. [4 seconds]",  # "dit-elle" is one word
        "Woman: «Merci», dit-elle. [3 seconds]",
        "Woman: «Merci», dit-elle. [3 seconds]",
    ]


def test_a_marked_lesson_above_a0_is_expanded_at_the_default_pace():
    from unittest.mock import patch

    from zeeguu.core.audio_lessons import script_generator

    raw = "At the café\n\n" + "\n".join(["Teacher: Ask for a coffee. [5 seconds]\nMan: En kaffe, tak. [answer]"] * 8)
    with patch.object(script_generator, "generate_script_in_languages", return_value=(raw, "model")):
        title, script, _, marked, reviewed = script_generator._write_dialogue_lesson(
            "prompt", None, origin_language="da", translation_language="en", suggestion="café",
            max_tokens=100, short_lines=False, marked=True,
        )
    assert title == "At the café"
    assert script.splitlines()[:3] == [
        "Teacher: Ask for a coffee. [6 seconds]",  # the model's 5 s dropped: 2 + 3.6 s
        "Man: En kaffe, tak. [3 seconds]",
        "Man: En kaffe, tak. [3 seconds]",
    ]
    assert marked.startswith("Teacher: Ask for a coffee. [5 seconds]\nMan: En kaffe, tak. [answer]")
    assert reviewed == ()


@pytest.mark.parametrize("prompt_file", ["dialogue_lesson--situation-v3.txt", "dialogue_lesson--topic-v3.txt"])
def test_the_dialogue_prompts_above_a0_are_marked_and_write_no_pauses(prompt_file):
    from zeeguu.core.audio_lessons.script_generator import MARKED_PROMPTS, get_prompt_template

    prompt = get_prompt_template(prompt_file)
    assert prompt_file in MARKED_PROMPTS
    assert "[answer]" in prompt and not re.search(r"\[[0-9.]+ seconds?\]", prompt)
    assert "TeacherL2" not in prompt  # never asked for in a dialogue, never written


@pytest.mark.parametrize("lesson_type", ["situation", "topic"])
def test_a_b1_dialogue_lesson_is_expanded(lesson_type):
    from unittest.mock import patch

    from zeeguu.core.audio_lessons import script_generator

    raw = "At the café\n\n" + "\n".join(["Teacher: Ask for a coffee.\nMan: En kaffe, tak. [answer]"] * 8)
    with patch.object(script_generator, "generate_script_in_languages", return_value=(raw, "model")):
        title, generated = script_generator.generate_dialogue_script("da", "en", "café", lesson_type, cefr_level="B1")
    assert title == "At the café"
    assert generated.marked is not None
    assert "[answer]" not in generated.script
    assert generated.challenges == ()


def test_a_marked_lesson_above_a0_without_its_answer_markers_is_rewritten_then_refused():
    from unittest.mock import patch

    from zeeguu.core.audio_lessons import script_generator

    unmarked = "Title\n\n" + "\n".join("Teacher: Ask for a coffee.\nMan: En kaffe, tak." for _ in range(12))
    with patch.object(script_generator, "generate_script_in_languages", return_value=(unmarked, "model")) as model:
        with pytest.raises(MarkupError, match=r"\[answer\]"):
            script_generator._write_dialogue_lesson(
                "prompt", None, origin_language="da", translation_language="en", suggestion="café",
                max_tokens=100, short_lines=False, marked=True,
            )
    assert model.call_count == script_generator.MARKUP_ATTEMPTS
    assert "[answer]" in model.call_args_list[-1].args[0]  # the rewrite is told why


def test_a_dialogue_above_a0_is_not_told_about_teacher_l2_but_a_word_lesson_is():
    from unittest.mock import patch

    from zeeguu.core.audio_lessons import script_generator

    raw = "Title\n\n" + "\n".join(["Teacher: Ask for a coffee.\nMan: En kaffe, tak. [answer]"] * 8)
    systems = []

    def model(prompt, **kwargs):
        systems.append(kwargs["system"])
        return raw, "model"

    with patch.object(script_generator, "generate_audio_lesson_script", model), patch.object(
        script_generator, "find_language_mismatches", lambda *a, **k: []
    ):
        script_generator.generate_dialogue_script("da", "en", "café", "topic", cefr_level="B1")
    assert "TeacherL2" not in systems[0]
    # Meaning lessons say the taught word on a TeacherL2: line
    assert "TeacherL2" in script_generator.language_contract("Danish", "English")
    assert "TeacherL2" not in script_generator._labels_note(["Mette"], teacher_l2=False)
    assert "TeacherL2" not in script_generator._correction_note([], "Danish", "English", teacher_l2=False)


@pytest.mark.parametrize("answer, a0_seconds, above_a0_seconds", [
    ("Tak.", 3, 5),  # one word: never under the 5 s every challenge had before
    ("Kan jeg få regningen?", 7, 7),
    ("Jeg vil gerne betale med kort, tak.", 10, 10),
    ("Meiner Meinung nach hat der Schiedsrichter einen großen Fehler gemacht.", 12, 10),  # 10 s at most
])
def test_above_a0_the_time_to_answer_is_between_five_and_ten_seconds(answer, a0_seconds, above_a0_seconds):
    from zeeguu.core.audio_lessons.script_generator import shared_lesson_values

    assert time_to_answer(answer, VALUES) == a0_seconds  # A0: as before
    assert time_to_answer(answer, shared_lesson_values()) == above_a0_seconds


def _written_above_a0(raw):
    from unittest.mock import patch

    from zeeguu.core.audio_lessons import script_generator

    with patch.object(script_generator, "generate_script_in_languages", return_value=(raw, "model")):
        return script_generator._write_dialogue_lesson(
            "prompt", None, origin_language="da", translation_language="en", suggestion="café",
            max_tokens=100, short_lines=False, marked=True,
        )


def test_above_a0_what_v2_scripts_were_forgiven_is_forgiven():
    challenge = "**Teacher:** Ask for a coffee,\nplease.\n---\nMan: En kaffe, tak. [answer] [3 seconds]\n"
    _, script, _, marked, _ = _written_above_a0("Title\n\n" + challenge * 8)
    assert script.splitlines()[:3] == [
        "Teacher: Ask for a coffee, please. [6 seconds]",  # unbolded, the wrapped line joined
        "Man: En kaffe, tak. [3 seconds]",  # an answer, though the model wrote a pause after it
        "Man: En kaffe, tak. [3 seconds]",
    ]
    assert "---" not in marked and "**" not in marked
