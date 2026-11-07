"""
A translation marked broken (the audit tool marks wrong-language ones) must not
be served from the #translated-from url cache: the next reader gets a fresh one,
saved at that same url. The broken one stays, for whoever has it open.
"""

from unittest import mock

from zeeguu.api.test.fixtures import create_and_get_article, logged_in_client
from zeeguu.core.llm_services.simplification_and_classification import (
    create_recipient_derivative,
    create_recipient_derivative_from_article,
)
from zeeguu.core.model import Article, Language
from zeeguu.core.model.article_broken_code_map import LowQualityTypes
from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.model.article_upload import ArticleUpload
from zeeguu.core.model.db import db


def _mock_llm(calls):
    def translate_and_adapt(self, **kwargs):
        calls.append(kwargs)
        n = len(calls)
        return {"title": f"Titre {n}", "content": f"Paragraphe {n}.", "summary": f"Résumé {n}"}

    return mock.patch(
        "zeeguu.core.llm_services.simplification_service."
        "SimplificationService.translate_and_adapt",
        translate_and_adapt,
    )


def _mark_broken(app, article_id):
    with app.app_context():
        Article.find_by_id(article_id).set_as_broken(
            db.session, LowQualityTypes.LLM_WRONG_LANGUAGE
        )


def _delete(app, article_ids):
    # Its own context: the one the test client keeps after a request can be gone.
    with app.app_context():
        for article_id in article_ids:
            article = Article.find_by_id(article_id)
            if article:
                ArticleFragment.query.filter_by(article_id=article.id).delete()
                db.session.delete(article)
        db.session.commit()


def _url_of(app, article_id):
    with app.app_context():
        return Article.find_by_id(article_id).url.as_string()


def _assert_replaced(app, broken_id, fresh_id, url):
    assert fresh_id != broken_id
    assert _url_of(app, fresh_id) == url
    assert _url_of(app, broken_id) == f"{url}-broken-{broken_id}"


def _translate_article(client, article_id):
    response = client.response_from_post(
        "/translate_and_adapt_article",
        data=dict(article_id=article_id, target_language="fr"),
    )
    assert response.status_code == 200
    return response.get_json()["id"]


def test_translate_and_adapt_article_replaces_a_broken_translation(app, logged_in_client):
    source_id = create_and_get_article(logged_in_client)["id"]
    with app.app_context():
        Language.find_or_create("fr")

    calls = []
    created = []
    with _mock_llm(calls):
        try:
            broken_id = _translate_article(logged_in_client, source_id)
            created.append(broken_id)
            url = _url_of(app, broken_id)

            # Still cached while it is fine.
            assert _translate_article(logged_in_client, source_id) == broken_id
            assert len(calls) == 1

            _mark_broken(app, broken_id)
            fresh_id = _translate_article(logged_in_client, source_id)
            created.append(fresh_id)

            assert len(calls) == 2
            _assert_replaced(app, broken_id, fresh_id, url)

            # The replacement is the cached one now.
            assert _translate_article(logged_in_client, source_id) == fresh_id
            assert len(calls) == 2
        finally:
            _delete(app, created)


def _create_upload(client, url):
    return client.post(
        "/article_upload/create",
        data=dict(
            url=url,
            title="Triumphbogen",
            text_content="Der Bau des Triumphbogens hat begonnen. Viele Leute sprechen darüber.",
        ),
    )["id"]


def test_upload_translate_and_adapt_replaces_a_broken_translation(app, logged_in_client):
    upload_id = _create_upload(logged_in_client, "https://example.com/broken/upload")

    def translate():
        response = logged_in_client.response_from_post(
            f"/article_upload/{upload_id}/translate_and_adapt"
        )
        assert response.status_code == 200
        return response.get_json()["id"]

    calls = []
    created = []
    with _mock_llm(calls):
        try:
            broken_id = translate()
            created.append(broken_id)
            url = _url_of(app, broken_id)

            _mark_broken(app, broken_id)
            fresh_id = translate()
            created.append(fresh_id)

            assert len(calls) == 2
            _assert_replaced(app, broken_id, fresh_id, url)
        finally:
            _delete(app, created)


def test_friend_share_copy_of_an_article_replaces_a_broken_one(app, logged_in_client):
    source_id = create_and_get_article(logged_in_client)["id"]

    def derive():
        with app.app_context():
            Language.find_or_create("fr")
            return create_recipient_derivative_from_article(
                db.session, Article.find_by_id(source_id), "fr", "A2"
            ).id

    calls = []
    created = []
    with _mock_llm(calls):
        try:
            broken_id = derive()
            created.append(broken_id)
            url = _url_of(app, broken_id)

            _mark_broken(app, broken_id)
            fresh_id = derive()
            created.append(fresh_id)

            assert len(calls) == 2
            _assert_replaced(app, broken_id, fresh_id, url)
        finally:
            _delete(app, created)


def test_friend_share_copy_of_an_upload_replaces_a_broken_one(app, logged_in_client):
    upload_id = _create_upload(logged_in_client, "https://example.com/broken/share")

    def derive():
        with app.app_context():
            Language.find_or_create("fr")
            return create_recipient_derivative(
                db.session, ArticleUpload.query.get(upload_id), "fr", "A2"
            ).id

    calls = []
    created = []
    with _mock_llm(calls):
        try:
            broken_id = derive()
            created.append(broken_id)
            url = _url_of(app, broken_id)

            _mark_broken(app, broken_id)
            fresh_id = derive()
            created.append(fresh_id)

            assert len(calls) == 2
            _assert_replaced(app, broken_id, fresh_id, url)
        finally:
            _delete(app, created)
