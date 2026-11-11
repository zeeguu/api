"""
Switching language with an article open translates it into the new language:
/translate_and_adapt_article with a target_language the user does not learn
yet. The translation is adapted to the user's level in that language, and
starts from the original even when the open article is a simplified or
translated version. Switching back to the original's language returns the
original, without a new translation.
"""

from unittest import mock

from zeeguu.api.test.fixtures import create_and_get_article, logged_in_client
from zeeguu.core import cefr
from zeeguu.core.model import Article, Language, User, UserLanguage
from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.model.db import db
from zeeguu.core.model.url import Url


def _mock_llm(calls):
    def translate_and_adapt(self, **kwargs):
        calls.append(kwargs)
        return {"title": "Venezuela", "content": "Premier paragraphe.", "summary": "Résumé"}

    return mock.patch(
        "zeeguu.core.llm_services.simplification_service."
        "SimplificationService.translate_and_adapt",
        translate_and_adapt,
    )


def _simplified_version_of(original, level=None):
    simplified = Article(
        Url.find_or_create(db.session, original.url.as_string() + "-a1"),
        "Venezuela, einfach",
        None,
        original.source,
        original.summary,
        original.published_time,
        None,
        original.language,
        "Ein einfacher Text.",
        None,
    )
    simplified.parent_article_id = original.id
    simplified.cefr_level = level
    db.session.add(simplified)
    db.session.commit()
    return simplified


def _set_level(user, language_code, level):
    user_language = UserLanguage.find_or_create(db.session, user, Language.find_or_create(language_code))
    user_language.cefr_level = cefr.to_number(level)
    db.session.add(user_language)
    db.session.commit()


def _translate(client, article_id, target_language):
    response = client.response_from_post(
        "/translate_and_adapt_article",
        data=dict(article_id=article_id, target_language=target_language),
    )
    assert response.status_code == 200
    return response.get_json()


def _delete(article_ids):
    for article_id in article_ids:
        article = Article.find_by_id(article_id)
        if article:
            ArticleFragment.query.filter_by(article_id=article.id).delete()
            db.session.delete(article)
    db.session.commit()


def _original_id(client):
    # An id, not the Article: an object loaded here is detached once the first
    # request ends its session.
    user = User.find("i@mir.lu")
    _set_level(user, "de", "B2")
    _set_level(user, "fr", "A2")
    _set_level(user, "es", "A2")
    return create_and_get_article(client)["id"]


def test_switching_back_returns_the_original_without_translating(logged_in_client):
    original_id = _original_id(logged_in_client)

    calls = []
    created = []
    with _mock_llm(calls):
        try:
            french = _translate(logged_in_client, original_id, "fr")
            created.append(french["id"])

            back = _translate(logged_in_client, french["id"], "de")

            assert back["id"] == original_id
            assert not back.get("is_translated")
            assert len(calls) == 1
        finally:
            _delete(created)


def test_switching_back_returns_the_simplified_version_at_the_users_level(
    logged_in_client,
):
    original_id = _original_id(logged_in_client)
    simplified_id = _simplified_version_of(Article.find_by_id(original_id), "B2").id

    calls = []
    created = [simplified_id]
    with _mock_llm(calls):
        try:
            french = _translate(logged_in_client, original_id, "fr")
            created.append(french["id"])

            back = _translate(logged_in_client, french["id"], "de")

            assert back["id"] == simplified_id
            assert len(calls) == 1
        finally:
            _delete(created)


def test_a_translation_is_translated_further_from_the_original(logged_in_client):
    original_id = _original_id(logged_in_client)
    original = Article.find_by_id(original_id)
    original_content = original.content
    original_url = original.url.as_string()

    calls = []
    created = []
    with _mock_llm(calls):
        try:
            french = _translate(logged_in_client, original_id, "fr")
            created.append(french["id"])

            spanish = _translate(logged_in_client, french["id"], "es")
            created.append(spanish["id"])

            assert calls[1]["content"] == original_content
            assert calls[1]["source_language"] == "de"
            url = Article.find_by_id(spanish["id"]).url.as_string()
            assert url == original_url + "#translated-from-de-to-es-A2"

            # Going back to a language already visited finds that translation.
            again = _translate(logged_in_client, spanish["id"], "fr")
            assert again["id"] == french["id"]
            assert len(calls) == 2
        finally:
            _delete(created)


def test_a_simplified_translation_goes_back_to_the_original(logged_in_client):
    original_id = _original_id(logged_in_client)

    calls = []
    created = []
    with _mock_llm(calls):
        try:
            french = _translate(logged_in_client, original_id, "fr")
            created.append(french["id"])
            simplified_id = _simplified_version_of(Article.find_by_id(french["id"])).id
            created.insert(0, simplified_id)

            back = _translate(logged_in_client, simplified_id, "de")

            assert back["id"] == original_id
            assert len(calls) == 1
        finally:
            _delete(created)


def test_an_article_adapted_in_its_own_language_is_still_adapted(logged_in_client):
    # The share flow's "Adapt" asks for the article's own language to change its
    # level. That is not a switch back, and must reach the LLM.
    original_id = _original_id(logged_in_client)

    calls = []
    created = []
    with _mock_llm(calls):
        try:
            adapted = _translate(logged_in_client, original_id, "de")
            created.append(adapted["id"])

            assert adapted["id"] != original_id
            assert len(calls) == 1
        finally:
            _delete(created)


def _article_at(url, like, language_code, content):
    article = Article(
        Url.find_or_create(db.session, url),
        "Stored article",
        None,
        like.source,
        like.summary,
        like.published_time,
        None,
        Language.find_or_create(language_code),
        content,
        None,
    )
    db.session.add(article)
    db.session.commit()
    return article.id


def test_an_old_translation_of_a_simplified_version_goes_back_to_the_original(
    logged_in_client,
):
    original_id = _original_id(logged_in_client)
    original = Article.find_by_id(original_id)
    simplified = _simplified_version_of(original)
    simplified_id = simplified.id
    old_translation_id = _article_at(
        simplified.url.as_string() + "#translated-from-de-to-fr-A2",
        original,
        "fr",
        "Un paragraphe.",
    )

    calls = []
    with _mock_llm(calls):
        try:
            back = _translate(logged_in_client, old_translation_id, "de")

            assert back["id"] == original_id
            assert calls == []
        finally:
            _delete([old_translation_id, simplified_id])


def test_translations_of_an_upload_never_reach_the_teaser_at_its_url(logged_in_client):
    # The upload holds the full text of an article we only have the teaser of.
    url = "https://example.com/switch/paywalled"
    teaser_id = _article_at(
        url,
        Article.find_by_id(_original_id(logged_in_client)),
        "de",
        "Nur der Anfang.",
    )
    upload_id = logged_in_client.post(
        "/article_upload/create",
        data=dict(
            url=url,
            title="Bezahlt",
            text_content="Der ganze Text steht hier. Er ist lang und bleibt auf Deutsch.",
        ),
    )["id"]

    calls = []
    created = []
    with _mock_llm(calls):
        try:
            first = logged_in_client.response_from_post(
                f"/article_upload/{upload_id}/translate_and_adapt"
            ).get_json()
            created.append(first["id"])
            french = _translate(logged_in_client, first["id"], "fr")
            created.append(french["id"])

            spanish = _translate(logged_in_client, french["id"], "es")
            created.append(spanish["id"])

            assert Article.find_by_id(french["id"]).source_upload_id == upload_id
            assert "Nur der Anfang." not in [call["content"] for call in calls]
            assert teaser_id not in [first["id"], french["id"], spanish["id"]]
        finally:
            _delete(created + [teaser_id])


def test_a_simplified_article_is_translated_from_its_original_at_the_target_level(
    logged_in_client,
):
    original = Article.find_by_id(create_and_get_article(logged_in_client)["id"])
    original_content = original.content
    simplified_id = _simplified_version_of(original).id
    user = User.find("i@mir.lu")
    _set_level(user, "de", "B2")
    _set_level(user, "fr", "A2")

    calls = []
    translated_id = None
    with _mock_llm(calls):
        try:
            response = logged_in_client.response_from_post(
                "/translate_and_adapt_article",
                data=dict(article_id=simplified_id, target_language="fr"),
            )
            assert response.status_code == 200
            translated_id = response.get_json()["id"]
            translated = Article.find_by_id(translated_id)

            assert len(calls) == 1
            assert calls[0]["content"] == original_content
            assert calls[0]["target_language"] == "fr"
            assert calls[0]["target_level"] == "A2"
            assert translated.language.code == "fr"
            assert translated.url.as_string().endswith("#translated-from-de-to-fr-A2")
        finally:
            for article_id in [translated_id, simplified_id]:
                article = Article.find_by_id(article_id) if article_id else None
                if article:
                    ArticleFragment.query.filter_by(article_id=article.id).delete()
                    db.session.delete(article)
            db.session.commit()
