"""Reading DeepSeek's verdict on a meaning lesson. Without a schema the reply
comes back in whatever shape the model chose, so the parser has to cope."""

import pytest

from zeeguu.core.audio_lessons.lesson_correctness_check import (
    FAIL,
    PASS,
    blocking,
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
        '{"verdict": "fail", "problems": [{"line": 6, "kind": "sense", "issue": "sådan is not a question word"}]}',
        LINES,
    )
    assert verdict == FAIL
    assert problems == [
        {"line": 6, "text": "Woman: Sådan gør du det?", "kind": "sense", "issue": "sådan is not a question word"}
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
    assert problems == [{"line": None, "text": None, "kind": "other", "issue": "wrong sense"}]


def test_unnatural_is_the_only_kind_that_does_not_block():
    _, problems = parse_lesson_verdict(
        '{"verdict": "fail", "problems": [{"line": 6, "kind": "Unnatural", "issue": "a"},'
        ' {"line": 6, "kind": "grammar", "issue": "b"}, {"line": 6, "kind": "made-up", "issue": "c"}]}',
        LINES,
    )
    assert [p["kind"] for p in problems] == ["unnatural", "grammar", "other"]
    assert [p["issue"] for p in blocking(problems)] == ["b", "c"]


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


def test_a_pair_reply_with_numbers_and_lists_is_still_read():
    from zeeguu.core.audio_lessons.lesson_correctness_check import second_opinion_on_meaning

    class Replies:
        model = "fake"

        def generate_text(self, *args, **kwargs):
            return '{"reason": "connu is known", "verdict": "fix", "corrected_word": "", ' \
                   '"corrected_translation": "known", "frequency": "common", "cefr": 2, ' \
                   '"phrase_type": "single_word", "explanation": ["formal"], "literal_meaning": null}'

    lesson = LessonToCheck(1, "fr", "en", "en", "connu", "experienced", 1, "Ce restaurant est connu.", "")
    verdict = second_opinion_on_meaning(Replies(), lesson)
    assert not verdict.is_valid
    assert verdict.corrected_translation == "known"


def test_a_pair_correction_listing_options_is_cut_to_one():
    from zeeguu.core.audio_lessons.lesson_correctness_check import second_opinion_on_meaning

    class Replies:
        model = "fake"

        def generate_text(self, *args, **kwargs):
            return '{"reason": "r", "verdict": "FIX", "corrected_word": "", ' \
                   '"corrected_translation": "which must/which should", "frequency": "common", ' \
                   '"cefr": "B1", "phrase_type": "single_word", "explanation": "", "literal_meaning": ""}'

    lesson = LessonToCheck(1, "da", "en", "en", "som skal", "who", 1, "Den som skal gå.", "")
    assert second_opinion_on_meaning(Replies(), lesson).corrected_translation == "which must"


def _deepseek_replying(text):
    class Replies:
        model = "fake"

        def generate_text(self, *args, **kwargs):
            return text

    return Replies()


def test_a_pair_correction_the_reply_says_does_not_fit_confirms_nothing():
    # The 13 Aug case, asked of DeepSeek: it writes "what it mean to walk",
    # judges it wrong, and still corrects to "mean"
    from zeeguu.core.audio_lessons.lesson_correctness_check import second_opinion_on_meaning

    reply = _deepseek_replying(
        '{"card_in_sentence": "", "card_reads_right": false, "reason": "r", "verdict": "FIX", '
        '"corrected_word": "vil sige", "corrected_translation": "mean", '
        '"correction_in_sentence": "I learned what it mean to walk", "correction_reads_right": false, '
        '"frequency": "common", "cefr": "A2", "phrase_type": "collocation", "explanation": "", "literal_meaning": ""}'
    )
    lesson = LessonToCheck(1, "da", "en", "en", "vil sige", "will say", 0,
                           "Jeg lærte, hvad det vil sige at gå", "")
    verdict = second_opinion_on_meaning(reply, lesson)
    assert verdict.gave_up == "WORD_NOT_FIT"
    assert verdict.corrected_translation is None


def test_a_pair_give_up_is_a_verdict_not_an_error():
    from zeeguu.core.audio_lessons.lesson_correctness_check import second_opinion_on_meaning

    reply = _deepseek_replying(
        '{"card_in_sentence": "", "card_reads_right": "false", "reason": "cut off", "verdict": "broken_sentence", '
        '"corrected_word": "særlig", "corrected_translation": "special", "correction_in_sentence": "", '
        '"correction_reads_right": "", "frequency": "common", "cefr": "B1", "phrase_type": "single_word", '
        '"explanation": "", "literal_meaning": ""}'
    )
    lesson = LessonToCheck(1, "da", "en", "en", "særl", "unusual", 0, "Det ganske særl", "")
    verdict = second_opinion_on_meaning(reply, lesson)
    assert verdict.verdict == "BROKEN_SENTENCE"
    assert verdict.corrected_word is None  # a give-up never moves the learner
    assert verdict.card_reads_right is False  # "false" as a string counts


def test_a_flag_written_as_a_string_still_counts():
    from zeeguu.core.audio_lessons.lesson_correctness_check import second_opinion_on_meaning

    reply = _deepseek_replying(
        '{"card_in_sentence": "", "card_reads_right": "", "reason": "r", "verdict": "FIX", '
        '"corrected_word": "vil sige", "corrected_translation": "mean", '
        '"correction_in_sentence": "I learned what it mean to walk", "correction_reads_right": "false", '
        '"frequency": "common", "cefr": "A2", "phrase_type": "collocation", "explanation": "", "literal_meaning": ""}'
    )
    lesson = LessonToCheck(1, "da", "en", "en", "vil sige", "will say", 0,
                           "Jeg lærte, hvad det vil sige at gå", "")
    assert second_opinion_on_meaning(reply, lesson).gave_up == "WORD_NOT_FIT"
