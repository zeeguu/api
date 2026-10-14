"""DeepSeek keeps a queued request alive by sending empty lines, which resets
requests' read timeout; the service's timeout must bound the whole request."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from zeeguu.core.llm_services.deepseek_service import DeepSeekService

ANSWER = json.dumps({"choices": [{"message": {"content": "hej"}}]}).encode()


def _fake_deepseek(keepalive_lines, body):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["content-length"]))
            self.send_response(200)
            self.end_headers()
            try:
                for _ in range(keepalive_lines):
                    self.wfile.write(b"\n")
                    self.wfile.flush()
                    time.sleep(0.2)
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the client gave up, as it should

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _service(server, timeout):
    service = DeepSeekService(api_key="test", timeout=timeout)
    service.base_url = f"http://127.0.0.1:{server.server_port}"
    return service


def _ask(service):
    return service._make_deepseek_request({"system": "s", "user": "u"}, max_tokens=5)


def test_answer_after_keepalive_lines_is_parsed():
    assert _ask(_service(_fake_deepseek(3, ANSWER), timeout=5)) == "hej"


def test_endless_keepalive_stops_at_the_deadline():
    service = _service(_fake_deepseek(100, ANSWER), timeout=1)
    start = time.monotonic()
    with pytest.raises(Exception, match="timeout"):
        _ask(service)
    assert time.monotonic() - start < 3


def test_body_without_choices_says_so():
    with pytest.raises(Exception, match="no choices"):
        _ask(_service(_fake_deepseek(0, b'{"error": "busy"}'), timeout=5))
