from types import SimpleNamespace

from zeeguu.core.llm_services import claude, models


def _block(type, **fields):
    return SimpleNamespace(type=type, **fields)


def test_text_is_read_by_block_type_not_position():
    # Sonnet 5.5 can start a reply with a thinking block, which has no .text
    response = SimpleNamespace(content=[
        _block("thinking", thinking=""),
        _block("text", text="VALID"),
    ])
    assert claude.response_text(response) == "VALID"


def test_sonnet_5_5_runs_without_thinking():
    assert claude.request_options("claude-sonnet-5-5") == {"thinking": {"type": "between_tools"}}


def test_haiku_5_5_thinks_a_little():
    assert claude.request_options("claude-haiku-5-5") == {
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "low"},
    }
    # thinking counts toward max_tokens, so a 30-token reply gets room for it
    assert claude.max_tokens("claude-haiku-5-5", 30) > 30


def test_other_models_get_nothing_they_would_reject():
    assert claude.request_options("claude-haiku-4-5-20251001") == {}
    assert claude.request_options("claude-sonnet-4-5-20250929") == {}
    assert claude.max_tokens("claude-sonnet-5-5", 30) == 30


def test_temperature_goes_only_to_models_that_take_it():
    assert claude.sampling_options("claude-haiku-4-5-20251001", 0.1) == {"extra_body": {"temperature": 0.1}}
    assert claude.sampling_options("claude-haiku-5-5", 0.1) == {}
    assert claude.sampling_options("claude-sonnet-5-5", 0.1) == {}


def test_every_sonnet_role_is_on_5_5():
    for role in (models.WORD_TRANSLATION, models.MWE_TRANSLATION, models.MWE_DETECTION,
                 models.TRANSLATION_VALIDATION, models.MEANING_FREQUENCY, models.ANTHROPIC_GENERAL):
        assert role == "claude-sonnet-5-5"
