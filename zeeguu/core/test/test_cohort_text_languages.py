from unittest import TestCase

import zeeguu.core
from zeeguu.core.model.cohort_article_map import CohortArticleMap
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.cohort_rule import CohortRule
from zeeguu.core.test.rules.language_rule import LanguageRule

db_session = zeeguu.core.model.db.session


class CohortTextLanguagesTest(ModelTestMixIn, TestCase):
    """Cohort.text_counts_by_language feeds the empty classroom.

    The classroom feed keeps only the texts whose language matches the
    student's learned language, so when it comes up empty the student needs to
    be told which language the class's texts are actually in. These counts are
    what that message is built from.
    """

    def setUp(self):
        super().setUp()
        self.cohort = CohortRule().cohort
        self.danish = LanguageRule().da
        self.german = LanguageRule().de

    def _share(self, article):
        db_session.add(CohortArticleMap(self.cohort, article, None))
        db_session.commit()

    def _article_in(self, language):
        article = ArticleRule().article
        article.language = language
        db_session.add(article)
        db_session.commit()
        return article

    def test_empty_cohort_reports_nothing(self):
        self.assertEqual([], self.cohort.text_counts_by_language())

    def test_counts_texts_per_language(self):
        self._share(self._article_in(self.danish))
        self._share(self._article_in(self.danish))
        self._share(self._article_in(self.german))

        counts = self.cohort.text_counts_by_language()

        self.assertEqual(
            {"da": 2, "de": 1}, {each["code"]: each["count"] for each in counts}
        )

    def test_biggest_language_comes_first(self):
        # The empty classroom offers one switch per language; the one with the
        # most texts behind it is the one worth offering first.
        self._share(self._article_in(self.german))
        self._share(self._article_in(self.danish))
        self._share(self._article_in(self.danish))

        counts = self.cohort.text_counts_by_language()

        self.assertEqual(["da", "de"], [each["code"] for each in counts])

    def test_ignores_texts_shared_with_other_cohorts(self):
        other_cohort = CohortRule().cohort
        db_session.add(CohortArticleMap(other_cohort, self._article_in(self.german), None))
        db_session.commit()

        self._share(self._article_in(self.danish))

        counts = self.cohort.text_counts_by_language()

        self.assertEqual([{"code": "da", "name": "Danish", "count": 1}], counts)
