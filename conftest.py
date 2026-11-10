"""
Root pytest configuration.

Only job for now: make a plain `pytest` run locally behave like the one in CI.
"""

import ipaddress
import os
import socket

import pytest

# The translation endpoints call out to Google/Microsoft/DeepL unless this is set,
# which means that on any machine without translator API keys every test that
# translates a word fails with a config error. CI exports it before pytest
# (.github/workflows/test.yml); doing it here means a local run doesn't have to
# know that. `setdefault`, so exporting DEV_SKIP_TRANSLATION=0 still lets you
# exercise the real translators on purpose.
os.environ.setdefault("DEV_SKIP_TRANSLATION", "1")

# Tokenization goes to the Stanza service, which tests fake in-process
# (zeeguu/core/test/fake_stanza_service.py). Set before anything imports the
# client, which reads the URL at import. Any value works: whatever it is, the
# mock answers it, so no real service is needed or contacted.
os.environ.setdefault("STANZA_SERVICE_URL", "http://stanza.test")

# Tests run offline. Two layers:
#
# 1. Drop the Anthropic keys. A developer's shell usually exports them, and
#    with them every test that creates an article or reports an exercise called
#    the real API (until Nov 2026: up to ~240 paid calls per full run, ~2.5s
#    each, nondeterministic, and a different code path from CI, which has no
#    keys).
#
# 2. Block every outbound connection, and fail the test that tried. Layer 1
#    only covers the clients we know about; this catches the next one. Blocking
#    alone is not enough: every LLM path falls back on a connection error, so a
#    leaking test would still pass. Hence the explicit failure, naming the host.
#
# ZEEGUU_TEST_ALLOW_NETWORK=1 turns both off, for when you mean to exercise
# the real services.
_ALLOW_NETWORK = os.environ.get("ZEEGUU_TEST_ALLOW_NETWORK") == "1"

if not _ALLOW_NETWORK:
    for _key in [k for k in os.environ if k.startswith("ANTHROPIC_")]:
        del os.environ[_key]


_network_attempts = []  # (test id, host), appended by the guards below


def _is_local(host):
    if host in ("localhost", "", None):
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _blocked(host):
    test = os.environ.get("PYTEST_CURRENT_TEST", "outside any test").split(" ")[0]
    _network_attempts.append((test, host))


if not _ALLOW_NETWORK:
    _real_connect = socket.socket.connect
    _real_getaddrinfo = socket.getaddrinfo

    def _guarded_connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not _is_local(address[0]):
            _blocked(address[0])
            raise ConnectionRefusedError(f"network blocked in tests: {address[0]}")
        return _real_connect(sock, address)

    def _guarded_getaddrinfo(host, *args, **kwargs):
        if isinstance(host, bytes):
            host = host.decode()
        if not _is_local(host):
            _blocked(host)
            raise socket.gaierror(f"network blocked in tests: {host}")
        return _real_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = _guarded_connect
    socket.getaddrinfo = _guarded_getaddrinfo


@pytest.fixture(autouse=True)
def _fail_on_network_access():
    before = len(_network_attempts)
    yield
    hosts = sorted({host for _, host in _network_attempts[before:]})
    if hosts:
        pytest.fail(
            f"test tried to reach {', '.join(hosts)}. Tests run offline: mock the "
            "call (see _mock_web), or set ZEEGUU_TEST_ALLOW_NETWORK=1 on purpose.",
            pytrace=False,
        )


def pytest_sessionfinish(session, exitstatus):
    # Attempts outside any test (collection, session fixtures) have no test to fail.
    outside = sorted({h for t, h in _network_attempts if t == "outside any test"})
    if outside:
        print(f"\nNetwork access outside any test, blocked: {', '.join(outside)}")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_configure(config):
    # bcrypt at the production 12 rounds costs ~0.17s per hash or verify, and
    # nearly every test creates and logs in a user: that was ~2/3 of the suite's
    # runtime. 4 is bcrypt's minimum; hashes stay real bcrypt and still verify.
    import zeeguu.core.util.hash

    zeeguu.core.util.hash.BCRYPT_ROUNDS = 4
