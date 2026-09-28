"""_content_from_ES_hits loads the rows behind search hits in bulk; it must
still hand them back in the hits' ranked order, one entry per hit."""
from unittest import TestCase

from sqlalchemy import event

import zeeguu.core
from zeeguu.core.content_recommender.elastic_recommender import _content_from_ES_hits
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule

session = zeeguu.core.model.db.session


def _hit(**source):
    return {"_source": source}


class ContentFromEsHitsTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.articles = [ArticleRule().article for _ in range(3)]
        session.commit()

    def test_keeps_the_ranking_and_marks_missing_rows(self):
        a, b, c = self.articles
        missing_article_id = max(x.id for x in self.articles) + 1000
        # Deliberately not in id order: the IN query would return id order.
        hits = [
            _hit(article_id=c.id),
            _hit(video_id=987654),  # a video whose row is gone
            _hit(article_id=a.id),
            _hit(article_id=missing_article_id),
            _hit(article_id=b.id),
        ]

        result = _content_from_ES_hits(hits)

        assert result == [c, None, a, None, b]

    def test_one_query_per_kind_not_per_hit(self):
        hits = [_hit(article_id=x.id) for x in self.articles] + [
            _hit(video_id=987654)
        ]
        session.expire_all()
        bind = session.get_bind()
        statements = []

        def on_execute(conn, cursor, statement, *rest):
            statements.append(statement)

        event.listen(bind, "before_cursor_execute", on_execute)
        try:
            _content_from_ES_hits(hits)
        finally:
            event.remove(bind, "before_cursor_execute", on_execute)

        from_article = [s for s in statements if "\nFROM article " in s]
        from_video = [s for s in statements if "\nFROM video " in s]
        assert len(from_article) == 1, from_article
        assert len(from_video) == 1, from_video

    def test_no_hits(self):
        assert _content_from_ES_hits([]) == []
