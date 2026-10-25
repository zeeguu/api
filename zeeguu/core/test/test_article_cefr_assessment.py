from unittest import mock

from sqlalchemy.orm import Query

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.model import ArticleCefrAssessment
from zeeguu.core.model.db import db


class ArticleCefrAssessmentTest(ModelTestMixIn):
    def test_find_or_create_loses_the_insert_race(self):
        # A double tap on promote_to_article: the other request inserts the
        # row while this one is waiting on its LLM call, so this one's lookup
        # (from an older REPEATABLE READ snapshot) has already missed it.
        article = ArticleRule().article
        winner = ArticleCefrAssessment.find_or_create(db.session, article.id)
        winner.set_ml_assessment("B1", "ml")
        db.session.commit()

        real_first = Query.first
        lookups = []

        def first_lookup_misses(query):
            lookups.append(query)
            if len(lookups) == 1:
                return None
            return real_first(query)

        with mock.patch.object(Query, "first", first_lookup_misses):
            loser = ArticleCefrAssessment.find_or_create(
                db.session, article.id, commit=False
            )
        loser.set_llm_assessment("B2", "llm_assessed_anthropic")
        db.session.commit()

        assert loser.article_id == article.id
        rows = ArticleCefrAssessment.query.filter_by(article_id=article.id).all()
        assert len(rows) == 1
        assert rows[0].ml_cefr_level == "B1"
        assert rows[0].llm_cefr_level == "B2"
