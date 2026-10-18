"""A meaning lesson script is checked before it is stored, rewritten once when
the check finds problems, and refused when the pair itself is wrong."""
from unittest.mock import patch

import pytest

from zeeguu.core.audio_lessons import script_generator
from zeeguu.core.audio_lessons.script_generator import LessonNotCorrect, generate_lesson_script

SENSE = {"line": 6, "text": "Woman: Sådan gør du det?", "kind": "sense", "issue": "how is hvordan"}
UNNATURAL = {"line": 7, "text": "Man: Sådan.", "kind": "unnatural", "issue": "stilted"}
TRANSLATION = {"line": 0, "text": None, "kind": "translation", "issue": "not 'how'"}


def run(verdicts, context="Sådan bruger en ekspert mindre tid på sin telefon"):
    """Generate with the LLM and the checker replaced; returns the result (or
    the exception) and the prompts the generator was given."""
    prompts = []

    def generate(prompt, **kwargs):
        prompts.append(prompt)
        return f"script {len(prompts)}", "fake-model"

    judged = iter(verdicts)

    def judge(service, lesson):
        verdict = next(judged)
        if isinstance(verdict, Exception):
            raise verdict
        return ("fail" if verdict else "pass"), verdict

    with patch.object(script_generator, "generate_script_in_languages", generate), patch(
        "zeeguu.core.audio_lessons.lesson_correctness_check.judge_lesson", judge
    ), patch("zeeguu.core.llm_services.deepseek_service.DeepSeekService", lambda: None):
        try:
            result = generate_lesson_script("Sådan", "How", "da", "en", context=context)
        except LessonNotCorrect as e:
            result = e
    return result, prompts


def test_a_passing_script_is_kept_and_the_prompt_carries_the_sentence():
    result, prompts = run([[]])
    assert result.script == "script 1"
    assert result.prompt_version == "meaning_lesson-v6"
    assert '"Sådan bruger en ekspert mindre tid på sin telefon"' in prompts[0]


def test_minor_problems_do_not_block():
    result, prompts = run([[UNNATURAL]])
    assert result.script == "script 1"
    assert len(prompts) == 1


def test_a_failing_script_is_rewritten_with_the_findings():
    result, prompts = run([[SENSE], []])
    assert result.script == "script 2"
    assert "Woman: Sådan gør du det?: how is hvordan" in prompts[1]


def test_a_script_still_wrong_after_the_rewrite_is_refused():
    result, prompts = run([[SENSE], [SENSE]])
    assert isinstance(result, LessonNotCorrect)
    assert len(prompts) == 2


def test_a_wrong_pair_is_refused_without_a_rewrite():
    result, prompts = run([[TRANSLATION]])
    assert isinstance(result, LessonNotCorrect)
    assert len(prompts) == 1


def test_an_unavailable_checker_lets_the_script_through():
    result, _ = run([Exception("DeepSeek API timeout")])
    assert result.script == "script 1"


def test_without_a_sentence_the_prompt_says_so():
    _, prompts = run([[]], context=None)
    assert "is not available" in prompts[0]
