from unittest import TestCase

import zeeguu.core
from zeeguu.core.model.cohort_article_map import CohortArticleMap
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.cohort_rule import CohortRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.user_rule import UserRule

db_session = zeeguu.core.model.db.session


class CohortArticleAttributionTest(ModelTestMixIn, TestCase):
    """cohort_articles_for_user says which class each text came from.

    A student in several classes gets one merged list; without the tag it is a
    pile of texts with no way to tell whose lesson is whose.
    """

    def setUp(self):
        super().setUp()
        self.danish = LanguageRule().da
        self.german = LanguageRule().de
        self.student = UserRule().user
        self.student.set_learned_language(self.danish.code, session=db_session)

    def _class_with(self, *articles):
        cohort = CohortRule().cohort
        for article in articles:
            db_session.add(CohortArticleMap(cohort, article, None))
        self.student.add_user_to_cohort(cohort, db_session)
        db_session.commit()
        return cohort

    def _article_in(self, language):
        article = ArticleRule().article
        article.language = language
        db_session.add(article)
        db_session.commit()
        return article

    def test_each_text_names_its_class(self):
        cohort = self._class_with(self._article_in(self.danish))

        infos = self.student.cohort_articles_for_user()

        self.assertEqual(1, len(infos))
        self.assertEqual([{"id": cohort.id, "name": cohort.name}], infos[0]["from_classes"])

    def test_a_text_in_two_classes_appears_once_naming_both(self):
        shared = self._article_in(self.danish)
        first = self._class_with(shared)
        second = self._class_with(shared)

        infos = self.student.cohort_articles_for_user()

        self.assertEqual(1, len(infos))
        self.assertEqual(
            {first.id, second.id},
            {each["id"] for each in infos[0]["from_classes"]},
        )

    def test_off_language_texts_are_still_left_out(self):
        self._class_with(self._article_in(self.german))

        self.assertEqual([], self.student.cohort_articles_for_user())
