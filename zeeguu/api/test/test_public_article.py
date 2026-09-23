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
    # find_or_create_article may credit the requesting user as uploader; these
    # tests want a plain crawled article unless they say otherwise.
    article = Article.find_by_id(article_id)
    article.uploader_id = None
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


def test_uploaded_text_opens_only_through_its_share_link(client, article_id):
    from zeeguu.core.model import User

    article = Article.find_by_id(article_id)
    article.uploader_id = User.find(client.email).id
    db.session.commit()

    status, _ = _anon_get(client, f"/public_article/{article_id}")
    assert status == 404

    code = client.post(f"/article_share_link/{article_id}")["code"]
    status, info = _anon_get(client, f"/public_article/{article_id}?s={code}")
    assert status == 200
    assert "uploader_name" not in info


def test_public_translate_persists_nothing(client, article_id):
    bookmarks_before = Bookmark.query.count()
    with patch("zeeguu.api.endpoints.public_article.IS_DEV_SKIP_TRANSLATION", False), patch(
        "zeeguu.api.endpoints.public_article.get_best_translation",
        return_value={"translation": "behind", "source": "Test", "likelihood": 1},
    ):
        response = client.client.post(
            "/public_translate_word/de/en",
            json={"word": "hinter,", "context": "hinter dem Haus"},
        )
    assert response.status_code == 200
    assert json.loads(response.data) == {"translation": "behind", "source": "Test"}
    assert Bookmark.query.count() == bookmarks_before


def test_public_translate_is_rate_limited(client):
    limiter = get_limiter()
    limiter.enabled = True
    try:
        with patch(
            "zeeguu.api.endpoints.public_article.get_best_translation",
            return_value={"translation": "x", "source": "Test"},
        ):
            codes = [
                client.client.post(
                    "/public_translate_word/de/en",
                    json={"word": "Haus"},
                    headers={"X-Forwarded-For": "203.0.113.50"},
                ).status_code
                for _ in range(21)
            ]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:20] == [200] * 20
    assert codes[20] == 429
