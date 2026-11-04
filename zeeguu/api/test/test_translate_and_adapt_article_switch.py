"""
Switching language with an article open translates it into the new language:
/translate_and_adapt_article with a target_language the user does not learn
yet. The translation is adapted to the user's level in that language, and
starts from the original even when the open article is a simplified version.
"""

from unittest import mock

from zeeguu.api.test.fixtures import create_and_get_article, logged_in_client
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


def _simplified_version_of(original):
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
    db.session.add(simplified)
    db.session.commit()
    return simplified


def _set_level(user, language_code, level):
    user_language = UserLanguage.find_or_create(db.session, user, Language.find_or_create(language_code))
    user_language.cefr_level = User.CEFR_LEVELS.index(level)
    db.session.add(user_language)
    db.session.commit()


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
