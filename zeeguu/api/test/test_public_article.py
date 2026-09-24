"""Account-less reading of a shared article: the public page's endpoints.

Articles are addressed by a random public code, never by numeric id:
zeeguu.org/read/<code>."""

import json
from unittest.mock import patch

import pytest

from fixtures import logged_in_client as client
from fixtures import add_context_types, add_source_types, create_and_get_article
from zeeguu.api.utils.rate_limiter import get_limiter
from zeeguu.core.model import Bookmark, User
from zeeguu.core.model.article_share_link import ArticleShareLink
from zeeguu.core.model.db import db


def _anon_get(client, url):
    """GET without the session the LoggedInClient helper would append."""
    response = client.client.get(url)
    return response.status_code, json.loads(response.data)


@pytest.fixture
def article_id(client):
    add_source_types()
    add_context_types()
    return create_and_get_article(client)["id"]


@pytest.fixture
def link(client, article_id):
    """The article's public code -- what follows /read/ in its link."""
    return client.post(f"/article_link/{article_id}")["code"]


# --- links -------------------------------------------------------------------


def test_code_is_ten_letters_and_digits_and_stable(client, article_id, link):
    assert len(link) == 10 and link.isalnum() and link.isascii()
    # Written once: asking again (every time the reader opens) returns the same code.
    assert client.post(f"/article_link/{article_id}")["code"] == link


def test_code_resolves_to_the_article(client, article_id, link):
    status, info = _anon_get(client, f"/article_link_info/{link}")
    assert (status, info) == (200, {"article_id": article_id})
    status, _ = _anon_get(client, "/article_link_info/doesNotExist")
    assert status == 404


def test_link_preview_for_preview_bots(client, article_id, link):
    with patch("zeeguu.api.endpoints.article._ensure_article_card"):
        response = client.client.get(f"/shared_article_preview/read/{link}")
    assert response.status_code == 200
    html = response.data.decode()
    assert f'<meta property="og:url" content="https://zeeguu.org/read/{link}">' in html
    assert f"/shared_article_image/{article_id}.jpg" in html


def test_legacy_share_code_translates_to_the_article_code(client, article_id, link):
    user = User.find(client.email)
    db.session.add(ArticleShareLink(code="oldCode123", user_id=user.id, article_id=article_id))
    db.session.commit()

    status, info = _anon_get(client, f"/article_share_link_info/oldCode123?article_id={article_id}")
    assert (status, info) == (200, {"code": link})

    status, _ = _anon_get(client, f"/article_share_link_info/oldCode123?article_id={article_id + 1}")
    assert status == 404


# --- reading -------------------------------------------------------------------


def test_article_opens_by_code_without_a_session(client, article_id, link):
    status, info = _anon_get(client, f"/public_article/{link}")
    assert status == 200
    assert info["id"] == article_id
    assert info["tokenized_fragments"]
    assert all(f["past_bookmarks"] == [] for f in info["tokenized_fragments"])
    assert info["tokenized_title_new"]["past_bookmarks"] == []
    assert "uploader_name" not in info


@pytest.mark.parametrize("bad", ["", "wrongCode1"])
def test_unknown_codes_and_numeric_ids_open_nothing(client, article_id, link, bad):
    assert client.client.get(f"/public_article/{bad or article_id}").status_code == 404


# --- translating -------------------------------------------------------------


def _positions(client, link, n):
    """The first n translatable word positions, across fragments."""
    _, info = _anon_get(client, f"/public_article/{link}")
    tokens = [
        (fragment["context_identifier"]["article_fragment_id"], t)
        for fragment in info["tokenized_fragments"]
        for par in fragment["tokens"]
        for sent in par
        for t in sent
        if not t["is_punct"]
    ]
    return [
        dict(part=part, paragraph_i=t["paragraph_i"], sent_i=t["sent_i"], token_i=t["token_i"], total_tokens=1)
        for part, t in tokens[:n]
    ], [t for _, t in tokens]


def _translate(client, link, position, headers=None):
    return client.client.post(f"/public_translate/{link}/en", json=position, headers=headers or {})


@pytest.fixture
def fake_translator():
    with patch("zeeguu.api.endpoints.public_article.IS_DEV_SKIP_TRANSLATION", False), patch(
        "zeeguu.api.endpoints.public_article.get_best_translation",
        side_effect=lambda word, *a, **k: {
            "translation": f"<{word}>",
            "source": "Test",
            "alternatives": [{"translation": f"<{word}>", "source": "Test", "votes": 3}],
        },
    ) as translator:
        yield translator


def test_translates_the_word_at_a_position_and_caches_it(client, link, fake_translator):
    bookmarks_before = Bookmark.query.count()
    (position,), tokens = _positions(client, link, 1)

    first = _translate(client, link, position)
    assert first.status_code == 200
    assert json.loads(first.data)["translation"] == f"<{tokens[0]['text']}>"

    second = _translate(client, link, position)
    assert json.loads(second.data) == json.loads(first.data)
    assert fake_translator.call_count == 1  # the second tap was a cache hit
    assert Bookmark.query.count() == bookmarks_before


def test_translating_needs_a_real_link(client, article_id, link, fake_translator):
    (position,), _ = _positions(client, link, 1)
    assert _translate(client, str(article_id), position).status_code == 404
    assert _translate(client, "wrongCode1", position).status_code == 404
    assert fake_translator.call_count == 0


@pytest.mark.parametrize(
    "position",
    [
        {},
        {"part": "title", "paragraph_i": 0, "sent_i": 0, "token_i": 999, "total_tokens": 1},
        {"part": "title", "paragraph_i": 0, "sent_i": 0, "token_i": 0, "total_tokens": 50},
        {"part": "title", "paragraph_i": "0", "sent_i": 0, "token_i": 0, "total_tokens": 1},
        {"part": 123456789, "paragraph_i": 0, "sent_i": 0, "token_i": 0, "total_tokens": 1},
        {"word": "Haus", "context": "anything I want translated"},
    ],
)
def test_rejects_positions_that_are_not_in_the_article(client, link, fake_translator, position):
    assert _translate(client, link, position).status_code == 400
    assert fake_translator.call_count == 0


@pytest.fixture
def limiting_enabled():
    limiter = get_limiter()
    limiter.enabled = True
    yield limiter
    limiter.enabled = False
    limiter.reset()


def test_global_ceiling_counts_only_cache_misses(client, link, fake_translator, limiting_enabled):
    from limits import parse

    positions, _ = _positions(client, link, 3)
    with patch("zeeguu.api.endpoints.public_article.GLOBAL_MISS_LIMIT", parse("2 per day")):
        # Different IPs, so only the global budget is in play.
        ip = lambda i: {"X-Forwarded-For": f"203.0.113.{i}"}
        assert _translate(client, link, positions[0], ip(1)).status_code == 200
        assert _translate(client, link, positions[1], ip(2)).status_code == 200
        assert _translate(client, link, positions[2], ip(3)).status_code == 429
        # Already-cached words keep working after the budget is spent.
        assert _translate(client, link, positions[0], ip(4)).status_code == 200


def test_per_ip_limit(client, link, fake_translator, limiting_enabled):
    (position,), _ = _positions(client, link, 1)
    headers = {"X-Forwarded-For": "203.0.113.50"}
    codes = [_translate(client, link, position, headers).status_code for _ in range(21)]
    assert codes[:20] == [200] * 20
    assert codes[20] == 429
