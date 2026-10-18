"""Reading DeepSeek's verdict on a meaning lesson. Without a schema the reply
comes back in whatever shape the model chose, so the parser has to cope."""

import pytest

from zeeguu.core.audio_lessons.lesson_correctness_check import (
    FAIL,
    PASS,
    LessonToCheck,
    checker_id,
    is_done,
    lesson_prompt,
    numbered_lines,
    parse_lesson_verdict,
)

SCRIPT = """Teacher: In the following conversation, you will hear the word: [0.2 seconds]
TeacherL2: Sådan [0.5 seconds]
Teacher: with the meaning [0.2 seconds]
Teacher: How. [1 seconds]

Teacher: Ask, how do you do it? [5 seconds]
Woman: Sådan gør du det? [3 seconds]
"""

LINES = numbered_lines(SCRIPT)


def test_lines_are_numbered_without_pauses_or_blanks():
    assert LINES == [
        "Teacher: In the following conversation, you will hear the word:",
        "TeacherL2: Sådan",
        "Teacher: with the meaning",
        "Teacher: How.",
        "Teacher: Ask, how do you do it?",
        "Woman: Sådan gør du det?",
    ]


def test_fail_resolves_each_line_to_its_text():
    verdict, problems = parse_lesson_verdict(
        '{"verdict": "fail", "problems": [{"line": 6, "issue": "sådan is not a question word"}]}',
        LINES,
    )
    assert verdict == FAIL
    assert problems == [
        {"line": 6, "text": "Woman: Sådan gør du det?", "issue": "sådan is not a question word"}
    ]


def test_pass_with_no_problems():
    assert parse_lesson_verdict('{"verdict": "pass", "problems": []}', LINES) == (PASS, [])


def test_fenced_reply_with_a_preamble():
    reply = 'Here is my review:\n```json\n{"verdict": "PASS", "problems": []}\n```'
    assert parse_lesson_verdict(reply, LINES) == (PASS, [])


@pytest.mark.parametrize("line", [6, "6", "L6", "line 6"])
def test_line_number_in_any_shape(line):
    _, problems = parse_lesson_verdict(
        f'{{"verdict": "fail", "problems": [{{"line": {line!r}, "issue": "x"}}]}}'.replace("'", '"'),
        LINES,
    )
    assert problems[0]["line"] == 6
    assert problems[0]["text"] == "Woman: Sådan gør du det?"


def test_whole_lesson_and_out_of_range_lines_have_no_text():
    _, problems = parse_lesson_verdict(
        '{"verdict": "fail", "problems": [{"line": 0, "issue": "a"}, {"line": 99, "issue": "b"}, {"issue": "c"}]}',
        LINES,
    )
    assert [(p["line"], p["text"]) for p in problems] == [(0, None), (99, None), (None, None)]


def test_a_pass_that_lists_problems_is_a_fail():
    verdict, problems = parse_lesson_verdict(
        '{"verdict": "pass", "problems": [{"line": 6, "issue": "unnatural"}]}', LINES
    )
    assert verdict == FAIL
    assert len(problems) == 1


def test_a_fail_without_problems_stays_a_fail():
    verdict, problems = parse_lesson_verdict('{"verdict": "fail", "problems": []}', LINES)
    assert verdict == FAIL
    assert problems[0]["issue"] == "(the model gave no reason)"


def test_problems_as_plain_strings():
    _, problems = parse_lesson_verdict('{"verdict": "fail", "problems": ["wrong sense"]}', LINES)
    assert problems == [{"line": None, "text": None, "issue": "wrong sense"}]


@pytest.mark.parametrize(
    "reply",
    [
        "The lesson looks fine.",
        '{"verdict": "maybe", "problems": []}',
        '{"problems": []}',
        '{"verdict": "pass", "problems": [',
        "[1, 2]",
    ],
)
def test_unusable_replies_raise(reply):
    with pytest.raises(ValueError):
        parse_lesson_verdict(reply, LINES)


def test_prompt_carries_word_translation_context_and_numbered_lines():
    lesson = LessonToCheck(
        id=41749,
        learned_language="da",
        teacher_language="en",
        translation_language="en",
        word="Sådan",
        translation="How",
        validated=1,
        context="Sådan bruger en ekspert mindre tid på sin telefon",
        script=SCRIPT,
    )
    prompt = lesson_prompt(lesson)
    assert 'Danish word "Sådan" with the meaning "How"' in prompt
    assert '"Sådan bruger en ekspert mindre tid på sin telefon"' in prompt
    assert "6: Woman: Sådan gør du det?" in prompt
    assert "may not generalize" in prompt


def test_only_current_checker_verdicts_count_as_done():
    current = checker_id("deepseek-chat")
    assert is_done({"checker": current, "verdict": FAIL}, current)
    assert not is_done({"checker": current, "verdict": "error"}, current)
    assert not is_done({"checker": "deepseek-chat:00000000", "verdict": PASS}, current)
    assert not is_done(None, current)
