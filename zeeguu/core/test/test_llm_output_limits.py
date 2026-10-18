"""
Output limits live with the model (models.MAX_OUTPUT_TOKENS), not at the call
sites: a caller asks for what its reply needs, and a model with a lower cap gets
its cap instead of rejecting the request. A reply cut off at the cap is a
failure, not an answer.
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


def _deepseek_answering(finish_reason):
    """DeepSeekService, with the suite's request mock answering its POST."""
    from zeeguu.core.test.conftest import get_mock

    service = DeepSeekService(api_key="test", timeout=5)
    get_mock().post(
        f"{service.base_url}/chat/completions",
        json={"choices": [{"message": {"content": "hej"}, "finish_reason": finish_reason}]},
    )
    return service


def test_deepseek_is_sent_its_cap_not_what_was_asked():
    from zeeguu.core.test.conftest import get_mock

    service = _deepseek_answering("stop")
    assert service.generate_text("u", max_tokens=16000) == "hej"
    assert get_mock().last_request.json()["max_tokens"] == 8192


def test_a_deepseek_reply_cut_off_at_the_cap_is_a_failure():
    service = _deepseek_answering("length")
    with pytest.raises(Exception, match="truncated at max_tokens=100"):
        service.generate_text("u", max_tokens=100)


def test_an_anthropic_reply_cut_off_at_the_cap_is_a_failure():
    service = AnthropicService(api_key="test")
    reply = SimpleNamespace(
        stop_reason="max_tokens", content=[SimpleNamespace(type="text", text="half a scri")]
    )
    service.client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: reply))
    with pytest.raises(Exception, match="truncated"):
        service.generate_text("u", max_tokens=100)


def test_an_anthropic_refusal_is_a_failure():
    service = AnthropicService(api_key="test")
    reply = SimpleNamespace(stop_reason="refusal", content=[])
    service.client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: reply))
    with pytest.raises(Exception, match="declined"):
        service.generate_text("u", max_tokens=100)
