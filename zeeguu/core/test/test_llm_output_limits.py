"""
Output limits live with the model (models.MAX_OUTPUT_TOKENS), not at the call
sites: a caller asks for what its reply needs, and a model with a lower cap gets
its cap instead of rejecting the request.
"""
from types import SimpleNamespace

import pytest

from zeeguu.core.llm_services import models
from zeeguu.core.llm_services.anthropic_service import AnthropicService
from zeeguu.core.llm_services.deepseek_service import DeepSeekService


def test_a_request_above_a_models_cap_gets_the_cap():
    assert models.output_tokens(models.DEEPSEEK_CHAT, 16000) == 8192
    assert models.output_tokens(models.DEEPSEEK_CHAT, 500) == 500
    # A model with no known cap is not capped here.
    assert models.output_tokens(models.ANTHROPIC_SONNET, 16000) == 16000


def test_deepseek_is_sent_its_cap_not_what_was_asked():
    from zeeguu.core.test.conftest import get_mock

    service = DeepSeekService(api_key="test", timeout=5)
    # An address of its own: the suite's request mock is shared by every test,
    # and a reply left on DeepSeek's real address would answer theirs.
    service.base_url = "https://deepseek.test-output-limits/v1"
    get_mock().post(
        f"{service.base_url}/chat/completions",
        json={"choices": [{"message": {"content": "hej"}, "finish_reason": "stop"}]},
    )
    assert service.generate_text("u", max_tokens=16000) == "hej"
    assert get_mock().last_request.json()["max_tokens"] == 8192


def test_anthropic_is_sent_what_was_asked_when_its_model_has_no_cap():
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="ok")])

    service = AnthropicService(api_key="test")
    service.client = SimpleNamespace(messages=SimpleNamespace(create=create))
    assert service.generate_text("u", max_tokens=16000) == "ok"
    assert sent["max_tokens"] == 16000
