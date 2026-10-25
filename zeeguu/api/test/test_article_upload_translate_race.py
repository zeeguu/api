"""
Two requests to /article_upload/<id>/translate_and_adapt for the same upload
(a double tap, or a retry while the first waits on the LLM) both miss the
existing-article lookup and both insert an article at the same url. The
loser used to hit the unique key on article.url_id and return a 500.
"""

from unittest import mock

from sqlalchemy.orm import Query

from zeeguu.api.test.fixtures import logged_in_client
from zeeguu.core.model import Article
from zeeguu.core.model.article_fragment import ArticleFragment
from zeeguu.core.model.db import db

UPLOAD_URL = "https://example.com/race/bau-von-trumps-triumphbogen"
TEXT = (
    "Der Bau des Triumphbogens hat begonnen. Er wird sechsundsiebzig Meter "
    "hoch sein und steht in der Hauptstadt. Viele Leute sprechen darüber."
)


def _llm_output():
    # Each call returns a different text, as the real LLM does: the loser's
    # fragments would differ from the winner's and add a second set.
    calls = []

    def translate_and_adapt(self, **kwargs):
        calls.append(kwargs)
        n = len(calls)
        return {
            "title": f"Triumphbogen {n}",
            "content": f"Erster Absatz, Version {n}.\n\nZweiter Absatz, Version {n}.",
            "summary": f"Zusammenfassung {n}",
        }

    return translate_and_adapt, calls


def _create_upload(client, url=UPLOAD_URL):
    upload = client.post(
        "/article_upload/create",
        data=dict(url=url, text_content=TEXT, title="Triumphbogen"),
    )
    return upload["id"]


def _translate(client, upload_id):
    return client.response_from_post(
        f"/article_upload/{upload_id}/translate_and_adapt"
    )


def _fragment_count(article_id):
    return ArticleFragment.query.filter_by(article_id=article_id).count()


def _articles_from(upload_id):
    return Article.query.filter_by(source_upload_id=upload_id).all()


def _cleanup(upload_id):
    # article and article_fragment survive between API tests (conftest's
    # _KEEP_TABLES), so remove what this test made.
    for article in _articles_from(upload_id):
        ArticleFragment.query.filter_by(article_id=article.id).delete()
        db.session.delete(article)
    db.session.commit()


def test_losing_the_insert_race_returns_the_winners_article(logged_in_client):
    upload_id = _create_upload(logged_in_client)
    translate_and_adapt, llm_calls = _llm_output()

    with mock.patch(
        "zeeguu.core.llm_services.simplification_service."
        "SimplificationService.translate_and_adapt",
        translate_and_adapt,
    ):
        try:
            # The winner: the first request creates the article.
            first = _translate(logged_in_client, upload_id)
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
                second = _translate(logged_in_client, upload_id)

            assert len(llm_calls) == 2, "the loser did reach the insert"
            assert second.status_code == 200
            assert second.get_json()["id"] == winner_id
            assert second.get_json()["title"] == "Triumphbogen 1"
            assert len(_articles_from(upload_id)) == 1
            assert _fragment_count(winner_id) == winner_fragments
        finally:
            _cleanup(upload_id)


def test_an_upload_whose_translated_url_is_too_long_gets_its_own_article(
    logged_in_client,
):
    # Url.find_or_create gives None for a path over 255 chars. These paths
    # fit, but not with the "#translated-from-de-to-de-A2" suffix, so both
    # translated articles get no url. Each must still get its own article,
    # not the other one (an `url_id IS NULL` lookup would find it).
    def long_url(n):
        path = f"/race/{n}-" + "x" * 240
        assert len(path) <= 255
        return "https://example.com" + path

    upload_ids = [_create_upload(logged_in_client, long_url(n)) for n in (1, 2)]
    translate_and_adapt, llm_calls = _llm_output()

    with mock.patch(
        "zeeguu.core.llm_services.simplification_service."
        "SimplificationService.translate_and_adapt",
        translate_and_adapt,
    ):
        try:
            responses = [_translate(logged_in_client, u) for u in upload_ids]

            assert [r.status_code for r in responses] == [200, 200]
            first, second = [r.get_json() for r in responses]
            assert first["id"] != second["id"]
            assert second["title"] == "Triumphbogen 2"
            for upload_id in upload_ids:
                [article] = _articles_from(upload_id)
                assert article.url is None
                assert _fragment_count(article.id) > 0
        finally:
            for upload_id in upload_ids:
                _cleanup(upload_id)
