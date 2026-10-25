"""
Two requests to /translate_and_adapt_article for the same article and level
(a double tap, or a retry while the first waits on the LLM) both miss the
existing-article lookup and both insert an article at the same url. The
loser used to hit the unique key on article.url_id and return a 500.
The sibling of test_article_upload_translate_race.py.
"""

from unittest import mock

from sqlalchemy.orm import Query

from zeeguu.api.test.fixtures import create_and_get_article, logged_in_client
from zeeguu.core.model import Article
from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.model.db import db


def _llm_output():
    # Each call returns a different text, as the real LLM does: the loser's
    # fragments would differ from the winner's and add a second set.
    calls = []

    def translate_and_adapt(self, **kwargs):
        calls.append(kwargs)
        n = len(calls)
        return {
            "title": f"Venezuela {n}",
            "content": f"Erster Absatz, Version {n}.\n\nZweiter Absatz, Version {n}.",
            "summary": f"Zusammenfassung {n}",
        }

    return translate_and_adapt, calls


def _mock_llm(translate_and_adapt):
    return mock.patch(
        "zeeguu.core.llm_services.simplification_service."
        "SimplificationService.translate_and_adapt",
        translate_and_adapt,
    )


def _translate(client, article_id):
    return client.response_from_post(
        "/translate_and_adapt_article", data=dict(article_id=article_id)
    )


def _fragment_count(article_id):
    return ArticleFragment.query.filter_by(article_id=article_id).count()


def _translations_of(source_path):
    # The translated article's url is the source's url plus
    # "#translated-from-...", and Article.url is a relationship, so match on
    # the stored path.
    path = source_path
    return [
        a
        for a in Article.query.filter(Article.url_id.isnot(None)).all()
        if a.url.path.startswith(path + "#translated-from-")
    ]


def _cleanup(articles):
    # article and article_fragment survive between API tests (conftest's
    # _KEEP_TABLES), so remove what this test made.
    for article in articles:
        ArticleFragment.query.filter_by(article_id=article.id).delete()
        db.session.delete(article)
    db.session.commit()


def test_losing_the_insert_race_returns_the_winners_article(logged_in_client):
    source_id = create_and_get_article(logged_in_client)["id"]
    source_path = Article.find_by_id(source_id).url.path
    translate_and_adapt, llm_calls = _llm_output()

    with _mock_llm(translate_and_adapt):
        try:
            # The winner: the first request creates the article.
            first = _translate(logged_in_client, source_id)
            assert first.status_code == 200
            winner_id = first.get_json()["id"]
            winner_fragments = _fragment_count(winner_id)
            assert winner_fragments > 0

            # The loser: its lookups miss the winner's article (on MySQL: its
            # REPEATABLE READ snapshot predates the winner's commit), so it
            # calls the LLM and inserts at the same url.
            real_one_or_none = Query.one_or_none
            article_lookups = []

            def first_article_lookup_misses(query):
                if query.column_descriptions[0]["entity"] is Article:
                    article_lookups.append(query)
                    if len(article_lookups) == 1:
                        return None
                return real_one_or_none(query)

            with mock.patch.object(Article, "find", return_value=None), \
                    mock.patch.object(Query, "one_or_none", first_article_lookup_misses):
                second = _translate(logged_in_client, source_id)

            assert len(llm_calls) == 2, "the loser did reach the insert"
            assert second.status_code == 200
            assert second.get_json()["id"] == winner_id
            assert second.get_json()["title"] == "Venezuela 1"
            assert len(_translations_of(source_path)) == 1
            assert _fragment_count(winner_id) == winner_fragments
        finally:
            _cleanup(_translations_of(source_path))


def test_an_article_whose_translated_url_is_too_long_gets_its_own_translation(
    logged_in_client,
):
    # Url.find_or_create gives None for a path over 255 chars. These paths
    # fit, but not with the "#translated-from-de-to-de-A1" suffix, so both
    # translated articles get no url. Each must still get its own article,
    # not the other one (an `url_id IS NULL` lookup would find it).
    from zeeguu.core.model.source import Source
    from zeeguu.core.model.source_type import SourceType
    from zeeguu.core.model.url import Url

    source_article = Article.find_by_id(create_and_get_article(logged_in_client)["id"])
    long_sources = []
    for n in (1, 2):
        path = f"/race/{n}-" + "x" * 240
        assert len(path) <= 255
        content = f"Text {n}. " + source_article.content
        source = Source.find_or_create(
            db.session,
            content,
            SourceType.find_by_type(SourceType.ARTICLE),
            source_article.language,
            0,
        )
        copy = Article(
            Url.find_or_create(db.session, "https://example.com" + path),
            source_article.title,
            None,
            source,
            source_article.summary,
            source_article.published_time,
            None,
            source_article.language,
            content,
            None,
        )
        db.session.add(copy)
        long_sources.append(copy)
    db.session.commit()
    source_ids = [a.id for a in long_sources]

    translate_and_adapt, llm_calls = _llm_output()
    responses = []
    with _mock_llm(translate_and_adapt):
        try:
            responses = [_translate(logged_in_client, i) for i in source_ids]

            assert [r.status_code for r in responses] == [200, 200]
            first, second = [r.get_json() for r in responses]
            assert first["id"] != second["id"]
            assert second["title"] == "Venezuela 2"
            for response in (first, second):
                article = Article.find_by_id(response["id"])
                assert article.url is None
                assert _fragment_count(article.id) > 0
        finally:
            translated = [
                Article.find_by_id(r.get_json()["id"])
                for r in responses
                if r.status_code == 200
            ]
            _cleanup(translated + [Article.find_by_id(i) for i in source_ids])
