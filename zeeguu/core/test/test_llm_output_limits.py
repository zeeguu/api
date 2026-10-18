"""
Output limits live with the model (models.MAX_OUTPUT_TOKENS), not at the call
sites: a caller asks for what its reply needs, and a model with a lower cap gets
its cap instead of rejecting the request. A reply cut off at the cap is a
failure, not an answer.
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
import requests_mock

from zeeguu.core.llm_services import models
from zeeguu.core.llm_services.anthropic_service import AnthropicService
from zeeguu.core.llm_services.deepseek_service import DeepSeekService


def test_a_request_above_a_models_cap_gets_the_cap():
    assert models.output_tokens(models.DEEPSEEK_CHAT, 16000) == 8192
    assert models.output_tokens(models.DEEPSEEK_CHAT, 500) == 500
    # A model with no known cap is not capped here.
    assert models.output_tokens(models.ANTHROPIC_SONNET, 16000) == 16000


def _fake_deepseek(finish_reason, sent):
    """A DeepSeek stand-in that records the request body it was sent."""
    body = json.dumps(
        {"choices": [{"message": {"content": "hej"}, "finish_reason": finish_reason}]}
    ).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            sent.append(json.loads(self.rfile.read(int(self.headers["content-length"]))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # the suite's shared requests_mock intercepts all HTTP; let this through
    from zeeguu.core.test.conftest import get_mock

    get_mock().register_uri(
        requests_mock.ANY,
        re.compile(rf"^http://127\.0\.0\.1:{server.server_port}/"),
        real_http=True,
    )
    service = DeepSeekService(api_key="test", timeout=5)
    service.base_url = f"http://127.0.0.1:{server.server_port}"
    return service


def test_deepseek_is_sent_its_cap_not_what_was_asked():
    sent = []
    service = _fake_deepseek("stop", sent)
    assert service.generate_text("u", max_tokens=16000) == "hej"
    assert sent[0]["max_tokens"] == 8192


def test_a_deepseek_reply_cut_off_at_the_cap_is_a_failure():
    service = _fake_deepseek("length", [])
    with pytest.raises(Exception, match="truncated"):
        service.generate_text("u", max_tokens=100)


def test_an_anthropic_reply_cut_off_at_the_cap_is_a_failure():
    service = AnthropicService(api_key="test")
    reply = SimpleNamespace(
        stop_reason="max_tokens", content=[SimpleNamespace(type="text", text="half a scri")]
    )
    service.client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: reply))
    with pytest.raises(Exception, match="truncated"):
        service.generate_text("u", max_tokens=100)
