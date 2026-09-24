from unittest import TestCase

import zeeguu.core
from zeeguu.core.classroom import hide_unshared_uploaded_texts
from zeeguu.core.model.cohort_article_map import CohortArticleMap
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.cohort_rule import CohortRule
from zeeguu.core.test.rules.user_rule import UserRule

db_session = zeeguu.core.model.db.session


class HideUnsharedUploadedTextsTest(ModelTestMixIn, TestCase):
    """An uploaded text reaches a student only through a class they are in now."""

    def setUp(self):
        super().setUp()
        self.student = UserRule().user
        self.teacher = UserRule().user

    def _crawled(self):
        article = ArticleRule().article
        article.uploader_id = None
        db_session.add(article)
        db_session.commit()
        return article

    def _uploaded(self):
        article = ArticleRule().article
        article.uploader_id = self.teacher.id
        db_session.add(article)
        db_session.commit()
        return article

    def _class_with(self, *articles, join=True):
        cohort = CohortRule().cohort
        for article in articles:
            db_session.add(CohortArticleMap(cohort, article, None))
        if join:
            self.student.add_user_to_cohort(cohort, db_session)
        db_session.commit()

    def test_crawled_articles_always_pass(self):
        crawled = self._crawled()
        self.assertEqual([crawled], hide_unshared_uploaded_texts(self.student, [crawled]))

    def test_uploaded_text_hidden_from_a_student_in_no_class(self):
        self.assertEqual([], hide_unshared_uploaded_texts(self.student, [self._uploaded()]))

    def test_uploaded_text_shown_when_shared_with_one_of_their_classes(self):
        shared, unshared = self._uploaded(), self._uploaded()
        self._class_with(shared)
        self.assertEqual([shared], hide_unshared_uploaded_texts(self.student, [shared, unshared]))

    def test_sharing_with_a_class_they_are_not_in_does_not_count(self):
        text = self._uploaded()
        self._class_with(text, join=False)
        self.assertEqual([], hide_unshared_uploaded_texts(self.student, [text]))

    def test_things_that_are_not_articles_pass(self):
        video = object()
        self.assertEqual([video], hide_unshared_uploaded_texts(self.student, [video]))
