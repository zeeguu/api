"""
Tuning a learner's next dialogue lessons from their feedback (lesson_tuning.py),
and the situations suggested for moving on (next_situations.py).
"""

from types import SimpleNamespace

import pytest

from zeeguu.core.audio_lessons.lesson_tuning import (
    LessonTuning,
    dialogue_prompt_values,
    is_valid,
    prompt_values,
    tuning_from,
)
from zeeguu.core.audio_lessons.next_situations import parse_suggestions
from zeeguu.core.audio_lessons.script_generator import (
    _normal_speed_example,
    get_prompt_template,
)


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


def _lesson_prompt(version, values=None):
    common = dict(
        target_language="Danish", source_language="English", cefr_level="A0",
        suggestion="at a café", history="Nothing yet.", dialogue="Man: Hej.",
        learner_role="Man",
    )
    template = get_prompt_template(f"a0_dialogue_lesson--pimsleur_style_situation-{version}.txt")
    if values is None:
        return template.format(**common)
    return template.format(
        **common, **values, normal_speed_example=_normal_speed_example("Man", values)
    )


def test_untuned_v2_prompt_is_exactly_v1():
    """A learner who never tapped anything gets the lesson they had before."""
    assert _lesson_prompt("v2", prompt_values(LessonTuning())) == _lesson_prompt("v1")


def test_faster_less_repetitive_shorter_prompt():
    prompt = _lesson_prompt("v2", prompt_values(LessonTuning(pace=2, repetition=2, length=2)))
    assert "[3 seconds] so the learner can answer" in prompt
    assert "Between repetitions, use [2 seconds]" in prompt
    assert "then once at normal speed" in prompt
    assert "about 2 times over the lesson" in prompt
    assert "At most 120 lines" in prompt and "about 7 minutes" in prompt
    # Words from earlier lessons come back less too ("tak", "hej").
    assert "come back once in the recalls" in prompt
    # The example drills the word once at normal speed, after the slow time.
    assert prompt.count("Man: <the word> [2 seconds]") == 3


def test_slower_prompt_gives_more_time():
    prompt = _lesson_prompt("v2", prompt_values(LessonTuning(pace=-2, repetition=-2)))
    assert "[7 seconds] so the learner can answer" in prompt
    assert "about 7 times over the lesson" in prompt


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


def test_length_and_repetition_are_separate():
    """A long lesson with little repetition: the length is the limit, repetition
    is how the lines inside it are spent."""
    values = prompt_values(LessonTuning(repetition=2, length=-2))
    assert values["max_lines"] == 250 and values["recalls_to_say"] == 2


def _dialogue_prompt(kind, version, tuning=None):
    common = dict(
        target_language="Danish", source_language="English", cefr_level="B1",
        suggestion="at a café",
    )
    template = get_prompt_template(f"dialogue_lesson--{kind}-{version}.txt")
    if tuning is None:
        return template.format(**common)
    values = dialogue_prompt_values(tuning)
    values["review_section"] = values["review_section"].format(**common)
    return template.format(**common, **values)


@pytest.mark.parametrize("kind", ["situation", "topic"])
def test_untuned_v3_dialogue_prompt_is_exactly_v2(kind):
    """Above A0 too, a learner who never tapped anything gets the lesson they
    had before, and such a dialogue can still be shared."""
    assert _dialogue_prompt(kind, "v3", LessonTuning()) == _dialogue_prompt(kind, "v2")


def test_faster_less_repetitive_shorter_dialogue_prompt():
    prompt = _dialogue_prompt("situation", "v3", LessonTuning(pace=2, repetition=2, length=2))
    assert "[3 seconds] after teacher questions" in prompt
    assert "use [2 seconds] between repeats" in prompt
    assert "<repeat same phrase>" not in prompt
    assert "said once after each challenge" in prompt
    assert "Never ask for the same phrase twice" in prompt
    assert "dialogue of about 8 lines" in prompt
    assert "Include about 4 challenges" in prompt
    assert "Add 2 more challenges" in prompt
    assert "over some of these again" not in prompt


def test_slower_more_repetitive_longer_dialogue_prompt():
    prompt = _dialogue_prompt("topic", "v3", LessonTuning(pace=-2, repetition=-2, length=-2))
    assert "[7 seconds] after teacher questions" in prompt
    assert prompt.count("Man: <repeat same phrase> [4 seconds]") == 2
    assert "ask 6 of the" in prompt and "but in English" in prompt
    assert "dialogue of about 24 lines" in prompt
    assert "Add 6 more challenges" in prompt
    assert "{" not in prompt


@pytest.mark.parametrize("aspect", ["pace", "repetition", "length"])
def test_every_dialogue_level_is_a_different_prompt(aspect):
    prompts = {
        _dialogue_prompt("situation", "v3", LessonTuning(**{aspect: level}))
        for level in (-2, -1, 0, 1, 2)
    }
    assert len(prompts) == 5
