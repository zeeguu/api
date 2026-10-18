"""
Caps on what one request, and one account per day, can make us spend on paid
LLM, machine translation and TTS calls -- and on the plain resource ceilings
around them: the request body size, Elasticsearch page sizes, and a tag-strip
regex that used to be quadratic.

Every cap here is checked before the paid call, so none of these tests needs
a provider mocked: a request that reaches the provider has already failed.
"""

import re
import time

import pytest

from zeeguu.api.test.fixtures import client, logged_in_client, LoggedInClient
from zeeguu.api.utils.input_limits import (
    MAX_CONTEXT_CHARS,
    MAX_OWN_TEXT_CHARS,
    MAX_PHRASE_CHARS,
)
from zeeguu.api.utils.rate_limiter import RATE_LIMITS, get_limiter


@pytest.fixture
def limiting_enabled():
    """The suite runs with the limiter off; switch it on for one test."""
    limiter = get_limiter()
    limiter.enabled = True
    yield limiter
    limiter.enabled = False
    limiter.reset()


def _too_long(cap):
    return "a" * (cap + 1)


# --- one account, one daily allowance -----------------------------------


def test_paid_endpoints_are_limited_per_account(app):
    """The point of key="user": a fresh login must not be a fresh allowance."""
    for endpoint in (
        "endpoints.ask_llm_translation",
        "endpoints.basic_translate",
        "endpoints.tts",
        "endpoints.generate_examples_for_word",
        "endpoints.judge_cloze_alternative",
        "endpoints.simplify_own_text",
        "endpoints.translate_and_adapt_article",
        "endpoints.article_upload_simplify",
        "endpoints.article_upload_translate_and_adapt",
    ):
        limit = RATE_LIMITS[endpoint]
        assert limit.key == "user", f"{endpoint} is not limited per account"
        assert "per day" in limit.rate, f"{endpoint} has no daily limit"


def test_full_article_audio_stops_at_the_daily_limit(client, limiting_enabled, _mock_web):
    """
    30 a day. Requests without an article id return before any TTS call,
    which is what lets this test run without one, and they still count.
    """
    reader = LoggedInClient(client, email="listener@zeeguu.test")

    codes = [
        reader.response_from_post("/mp3_of_full_article").status_code for _ in range(31)
    ]

    assert 429 not in codes[:30], "the limit fired before the 30th request"
    assert codes[30] == 429, "the 31st full-article request of the day went through"


def test_logging_in_again_does_not_reset_the_allowance(client, limiting_enabled, _mock_web):
    """A second device, or a script that logs in afresh, shares the same bucket."""
    reader = LoggedInClient(client, email="twodevices@zeeguu.test")
    for _ in range(30):
        reader.response_from_post("/mp3_of_full_article")

    second_session = client.post(
        "/session/twodevices@zeeguu.test", data={"password": "test"}
    ).get_json()["session"]
    response = client.post(f"/mp3_of_full_article?session={second_session}")

    assert response.status_code == 429


def test_one_account_spending_its_allowance_leaves_others_alone(
    client, limiting_enabled, _mock_web
):
    """A class shares an IP; the bucket must be the account's, not the room's."""
    first = LoggedInClient(client, email="first@zeeguu.test", username="first")
    for _ in range(31):
        first.response_from_post("/mp3_of_full_article")

    second = LoggedInClient(client, email="second@zeeguu.test", username="second")
    assert second.response_from_post("/mp3_of_full_article").status_code != 429


# --- length caps: 400 before the paid call ------------------------------


def test_llm_translation_refuses_an_overlong_word(logged_in_client):
    response = logged_in_client.response_from_post(
        "/ask_llm_translation/de/en",
        json={"word": _too_long(MAX_PHRASE_CHARS), "context": ""},
    )
    assert response.status_code == 400


def test_llm_translation_refuses_an_overlong_context(logged_in_client):
    response = logged_in_client.response_from_post(
        "/ask_llm_translation/de/en",
        json={"word": "Haus", "context": _too_long(MAX_CONTEXT_CHARS)},
    )
    assert response.status_code == 400


def test_word_translation_refuses_an_overlong_context(logged_in_client):
    response = logged_in_client.response_from_post(
        "/translate_word/de/en",
        json={"word": "Haus", "context": _too_long(MAX_CONTEXT_CHARS)},
    )
    assert response.status_code == 400


def test_basic_translate_refuses_an_overlong_phrase(logged_in_client):
    response = logged_in_client.response_from_post(
        "/basic_translate/de/en", data={"phrase": _too_long(MAX_PHRASE_CHARS)}
    )
    assert response.status_code == 400


def test_text_to_speech_refuses_an_overlong_text(logged_in_client):
    response = logged_in_client.response_from_post(
        "/text_to_speech",
        data={"text": _too_long(MAX_PHRASE_CHARS), "language_id": "de"},
    )
    assert response.status_code == 400


def test_cloze_judge_refuses_an_overlong_answer(logged_in_client):
    response = logged_in_client.response_from_post(
        "/judge_cloze_alternative",
        json={"bookmark_id": 1, "typed": _too_long(MAX_PHRASE_CHARS)},
    )
    assert response.status_code == 400


def test_simplify_own_text_refuses_an_overlong_text(logged_in_client):
    """Form bodies stop at 500 KB anyway, so send it as one under that."""
    response = logged_in_client.response_from_post(
        "/simplify_own_text",
        data={
            "title": "t",
            "content": _too_long(MAX_OWN_TEXT_CHARS),
            "language": "de",
            "cefr_level": "A2",
        },
    )
    assert response.status_code == 400
    assert "too long" in response.get_json()["message"]


# --- request body ceiling ------------------------------------------------


def test_request_bodies_have_a_ceiling(app):
    assert app.config["MAX_CONTENT_LENGTH"] is not None


def test_a_body_past_the_ceiling_is_refused(logged_in_client, app):
    oversized = b"x" * (app.config["MAX_CONTENT_LENGTH"] + 1)
    response = logged_in_client.client.post(
        logged_in_client.append_session("/ask_llm_translation/de/en"),
        data=oversized,
        content_type="application/json",
    )
    assert response.status_code == 413


def test_the_ceiling_admits_the_largest_flashcard_recording(app):
    """The biggest legitimate upload must still fit, envelope and all."""
    from zeeguu.api.endpoints.verbal_flashcards import MAX_VERBAL_FLASHCARD_AUDIO_BYTES

    assert app.config["MAX_CONTENT_LENGTH"] > MAX_VERBAL_FLASHCARD_AUDIO_BYTES


# --- the tag-strip regex ---------------------------------------------------


def test_tag_stripping_is_linear_on_unclosed_brackets():
    """
    "<[^>]*>" rescanned to the end of input from every "<": 20k of them took
    a tenth of a second, 500 KB over a minute. Now it must be instant.
    """
    from zeeguu.core.model.article import HTML_TAG_CLEANR

    start = time.time()
    re.sub(HTML_TAG_CLEANR, "", "<" * 400_000)
    assert time.time() - start < 1


def test_tag_stripping_still_strips_tags():
    from zeeguu.core.model.article import HTML_TAG_CLEANR

    html = '<p class="x">Hallo <b>Welt</b></p>'
    assert re.sub(HTML_TAG_CLEANR, "", html) == "Hallo Welt"


def test_language_check_survives_a_hostile_page(logged_in_client):
    start = time.time()
    response = logged_in_client.response_from_post(
        # 150k is what fits under the 500 KB form limit once urlencoded.
        "/is_article_language_supported", data={"htmlContent": "<" * 150_000}
    )
    assert response.status_code == 200
    assert time.time() - start < 5


# --- counts that become query sizes -----------------------------------------


def test_recommended_count_is_clamped(logged_in_client, monkeypatch):
    """The <count> in the route is the Elasticsearch size."""
    from zeeguu.api.endpoints import user_articles

    asked_for = {}

    def fake_recommendations(user, count, *args, **kwargs):
        asked_for["count"] = count
        return []

    monkeypatch.setattr(
        user_articles, "article_recommendations_for_user", fake_recommendations
    )

    logged_in_client.get("/user_articles/recommended/1000000")

    assert asked_for["count"] == user_articles.MAX_RECOMMENDED_COUNT


def test_recommended_count_below_the_cap_is_untouched(logged_in_client, monkeypatch):
    from zeeguu.api.endpoints import user_articles

    asked_for = {}

    def fake_recommendations(user, count, *args, **kwargs):
        asked_for["count"] = count
        return []

    monkeypatch.setattr(
        user_articles, "article_recommendations_for_user", fake_recommendations
    )

    logged_in_client.get("/user_articles/recommended/20")

    assert asked_for["count"] == 20


# --- where the counters live ---------------------------------------------------


def test_limiter_storage_defaults_to_memory(app, monkeypatch):
    from zeeguu.api.utils.rate_limiter import _storage_uri

    monkeypatch.delenv("RATELIMIT_STORAGE_URI", raising=False)
    monkeypatch.setitem(app.config, "RATELIMIT_STORAGE_URI", None)
    assert _storage_uri(app) == "memory://"


def test_limiter_storage_can_come_from_the_environment(app, monkeypatch):
    """docker-compose sets it as an environment variable, not in api.cfg."""
    from zeeguu.api.utils.rate_limiter import _storage_uri

    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://redis:6379/0")
    monkeypatch.setitem(app.config, "RATELIMIT_STORAGE_URI", None)
    assert _storage_uri(app) == "redis://redis:6379/0"


def test_the_config_file_wins_over_the_environment(app, monkeypatch):
    from zeeguu.api.utils.rate_limiter import _storage_uri

    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://from-env:6379/0")
    monkeypatch.setitem(app.config, "RATELIMIT_STORAGE_URI", "redis://from-cfg:6379/0")
    assert _storage_uri(app) == "redis://from-cfg:6379/0"


def test_the_logged_storage_uri_hides_the_password():
    from zeeguu.api.utils.rate_limiter import _redacted

    assert _redacted("redis://:s3cret@redis:6379/0") == "redis://:***@redis:6379/0"
    assert _redacted("memory://") == "memory://"
