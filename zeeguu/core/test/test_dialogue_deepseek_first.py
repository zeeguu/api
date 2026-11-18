"""
Dialogue lessons above A0 ask DeepSeek first, with Anthropic behind it.
No Flask app context, DB or network.
"""

from unittest.mock import patch

import pytest

from zeeguu.core.audio_lessons import script_generator
from zeeguu.core.llm_services.llm_service import UnifiedLLMService

SCRIPT = """A Title

Teacher: Two friends meet. [0.5 seconds]
Man: Hej! [1 seconds]
Woman: Hej! [1 seconds]
"""


def _dialogue_asks(cefr_level):
    seen = {}

    def generate(prompt, **kwargs):
        seen.update(kwargs)
        return SCRIPT, "model"

    with patch.object(script_generator, "generate_audio_lesson_script", generate), patch.object(
        script_generator, "find_language_mismatches", lambda *a, **k: []
    ), patch.object(script_generator, "_dialogue_for_beginner", lambda *a: script_generator.GeneratedScript("Man: Hej", "m", "v1")):
        script_generator.generate_dialogue_script("da", "en", "at the café", "situation", cefr_level=cefr_level)
    return seen.get("deepseek_first", False)


def test_a_dialogue_above_a0_asks_deepseek_first():
    assert _dialogue_asks("A1") is True


def test_an_a0_dialogue_keeps_anthropic_first():
    assert _dialogue_asks("A0") is False


class _Service:
    def __init__(self, model, fails=False):
        self.model, self.fails, self.calls = model, fails, 0

    def generate_text(self, *args):
        self.calls += 1
        if self.fails:
            raise Exception(f"{self.model} down")
        return f"from {self.model}"


def _unified(deepseek, anthropic):
    unified = UnifiedLLMService()
    unified.deepseek_service, unified.anthropic_service = deepseek, anthropic
    return unified


def test_deepseek_first_answers_from_deepseek():
    deepseek, anthropic = _Service("deepseek-chat"), _Service("claude")
    assert _unified(deepseek, anthropic).generate_text_with_model("p", deepseek_first=True) == (
        "from deepseek-chat",
        "deepseek-chat",
    )
    assert anthropic.calls == 0


def test_deepseek_first_falls_back_to_anthropic_and_says_so():
    deepseek, anthropic = _Service("deepseek-chat", fails=True), _Service("claude")
    assert _unified(deepseek, anthropic).generate_text_with_model("p", deepseek_first=True) == (
        "from claude",
        "claude",
    )


def test_deepseek_first_raises_when_both_fail():
    with pytest.raises(Exception, match="both APIs failed"):
        _unified(_Service("deepseek-chat", True), _Service("claude", True)).generate_text_with_model(
            "p", deepseek_first=True
        )


def test_the_default_order_is_unchanged():
    deepseek, anthropic = _Service("deepseek-chat"), _Service("claude")
    assert _unified(deepseek, anthropic).generate_text_with_model("p")[1] == "claude"
    assert deepseek.calls == 0
