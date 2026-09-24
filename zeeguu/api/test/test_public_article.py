"""Account-less reading of a shared article: the public page's endpoints."""

import json
from unittest.mock import patch

import pytest

from fixtures import logged_in_client as client
from fixtures import add_context_types, add_source_types, create_and_get_article
from zeeguu.api.utils.rate_limiter import get_limiter
from zeeguu.core.model import Article, Bookmark
from zeeguu.core.model.db import db


def _anon_get(client, url):
    """GET without the session the LoggedInClient helper would append."""
    response = client.client.get(url)
    return response.status_code, json.loads(response.data)


@pytest.fixture
def article_id(client):
    add_source_types()
    add_context_types()
    article_id = create_and_get_article(client)["id"]
    # A plain crawled article (from a feed, no uploader) unless a test says otherwise.
    from zeeguu.core.test.rules.feed_rule import FeedRule

    article = Article.find_by_id(article_id)
    article.uploader_id = None
    article.feed = FeedRule().feed
    db.session.commit()
    return article_id


def test_public_article_needs_no_session(client, article_id):
    status, info = _anon_get(client, f"/public_article/{article_id}")
    assert status == 200
    assert info["title"]
    assert info["tokenized_fragments"]
    assert all(f["past_bookmarks"] == [] for f in info["tokenized_fragments"])
    assert info["tokenized_title_new"]["past_bookmarks"] == []
    assert "shared_by_name" not in info


def test_share_link_is_stable_and_credits_the_sharer(client, article_id):
    first = client.post(f"/article_share_link/{article_id}")["code"]
    again = client.post(f"/article_share_link/{article_id}")["code"]
    assert first == again

    status, info = _anon_get(client, f"/public_article/{article_id}?s={first}")
    assert status == 200
    assert info["shared_by_name"] == "test"

    status, credit = _anon_get(client, f"/article_share_link_info/{first}?article_id={article_id}")
    assert status == 200 and credit["shared_by_name"] == "test"


def test_share_code_for_another_article_gives_no_credit(client, article_id):
    code = client.post(f"/article_share_link/{article_id}")["code"]
    status, _ = _anon_get(client, f"/article_share_link_info/{code}?article_id={article_id + 1}")
    assert status == 404


def test_web_article_without_feed_is_public(client, article_id):
    # Sent in from a browser / share sheet: no feed, but a real web URL.
    article = Article.find_by_id(article_id)
    article.feed = None
    db.session.commit()

    status, _ = _anon_get(client, f"/public_article/{article_id}")
    assert status == 200


def test_typed_text_opens_only_through_its_share_link(client, article_id):
    # A typed/pasted text: no feed and no web address (see _is_web_content).
    # No uploader either -- what a deleted account's texts look like.
    from zeeguu.core.model import Language

    typed_id = Article.create_from_upload(
        db.session,
        title="Mein Text",
        content="Das ist ein Text, den jemand selbst geschrieben hat.",
        htmlContent="<p>Das ist ein Text, den jemand selbst geschrieben hat.</p>",
        uploader=None,
        language=Language.find("de"),
    )

    status, _ = _anon_get(client, f"/public_article/{typed_id}")
    assert status == 404

    code = client.post(f"/article_share_link/{typed_id}")["code"]
    status, info = _anon_get(client, f"/public_article/{typed_id}?s={code}")
    assert status == 200
    assert "uploader_name" not in info


def _positions(client, article_id, n):
    """The first n translatable word positions of the article's first fragment."""
    _, info = _anon_get(client, f"/public_article/{article_id}")
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


def _translate(client, article_id, position, headers=None):
    return client.client.post(f"/public_translate/{article_id}/en", json=position, headers=headers or {})


@pytest.fixture
def fake_translator():
    with patch("zeeguu.api.endpoints.public_article.IS_DEV_SKIP_TRANSLATION", False), patch(
        "zeeguu.api.endpoints.public_article.get_best_translation",
        side_effect=lambda word, *a, **k: {"translation": f"<{word}>", "source": "Test", "alternatives": [{"translation": f"<{word}>", "source": "Test", "votes": 3}]},
    ) as translator:
        yield translator


def test_translates_the_word_at_a_position_and_caches_it(client, article_id, fake_translator):
    bookmarks_before = Bookmark.query.count()
    (position,), tokens = _positions(client, article_id, 1)

    first = _translate(client, article_id, position)
    assert first.status_code == 200
    assert json.loads(first.data)["translation"] == f"<{tokens[0]['text']}>"

    second = _translate(client, article_id, position)
    assert json.loads(second.data) == json.loads(first.data)
    assert fake_translator.call_count == 1  # the second tap was a cache hit
    assert Bookmark.query.count() == bookmarks_before


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
def test_rejects_positions_that_are_not_in_the_article(client, article_id, fake_translator, position):
    assert _translate(client, article_id, position).status_code == 400
    assert fake_translator.call_count == 0


def test_private_text_words_need_the_share_code(client, fake_translator):
    from zeeguu.core.model import Language

    typed_id = Article.create_from_upload(
        db.session,
        title="Mein Brief",
        content="Diesen Brief hat jemand zu Hause geschrieben.",
        htmlContent="<p>Diesen Brief hat jemand zu Hause geschrieben.</p>",
        uploader=None,
        language=Language.find("de"),
    )
    position = {"part": "title", "paragraph_i": 0, "sent_i": 0, "token_i": 0, "total_tokens": 1}
    assert _translate(client, typed_id, position).status_code == 404

    code = client.post(f"/article_share_link/{typed_id}")["code"]
    assert _translate(client, typed_id, {**position, "s": code}).status_code == 200


@pytest.fixture
def limiting_enabled():
    limiter = get_limiter()
    limiter.enabled = True
    yield limiter
    limiter.enabled = False
    limiter.reset()


def test_global_ceiling_counts_only_cache_misses(client, article_id, fake_translator, limiting_enabled):
    from limits import parse

    positions, _ = _positions(client, article_id, 3)
    with patch("zeeguu.api.endpoints.public_article.GLOBAL_MISS_LIMIT", parse("2 per day")):
        # Different IPs, so only the global budget is in play.
        ip = lambda i: {"X-Forwarded-For": f"203.0.113.{i}"}
        assert _translate(client, article_id, positions[0], ip(1)).status_code == 200
        assert _translate(client, article_id, positions[1], ip(2)).status_code == 200
        assert _translate(client, article_id, positions[2], ip(3)).status_code == 429
        # Already-cached words keep working after the budget is spent.
        assert _translate(client, article_id, positions[0], ip(4)).status_code == 200


def test_per_ip_limit(client, article_id, fake_translator, limiting_enabled):
    (position,), _ = _positions(client, article_id, 1)
    headers = {"X-Forwarded-For": "203.0.113.50"}
    codes = [_translate(client, article_id, position, headers).status_code for _ in range(21)]
    assert codes[:20] == [200] * 20
    assert codes[20] == 429
