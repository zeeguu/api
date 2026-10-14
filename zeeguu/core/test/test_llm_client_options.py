from zeeguu.core.llm_services import get_llm_service


def _clients(monkeypatch, **options):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    service = get_llm_service("unified", **options)
    return service._get_anthropic_service(), service._get_deepseek_service()


def test_interactive_options_reach_both_providers(monkeypatch):
    anthropic, deepseek = _clients(monkeypatch, timeout=20, max_retries=0)
    assert anthropic.client.timeout == 20
    assert anthropic.client.max_retries == 0
    assert deepseek.timeout == 20


def test_defaults_unchanged_for_background_callers(monkeypatch):
    anthropic, deepseek = _clients(monkeypatch)
    assert anthropic.client.timeout == 120
    assert anthropic.client.max_retries == 2
    assert deepseek.timeout == 120
