from datetime import datetime
from unittest import TestCase

import zeeguu.core
from zeeguu.core.model.user_cohort_map import UserCohortMap
from zeeguu.core.model.user_reading_session import UserReadingSession
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.cohort_rule import CohortRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.user_statistics.platform_totals import (
    MIN_ACTIVE_STUDENTS,
    MIN_READING_SESSIONS,
    compute_platform_totals,
)

db_session = zeeguu.core.model.db.session


class PlatformTotalsTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.article = ArticleRule().article
        self.class_rule = CohortRule()
        self.cohort = self.class_rule.cohort
        self.teacher = self.class_rule.teacher

    def _enrol(self, readers, sessions_each=MIN_READING_SESSIONS):
        for _ in range(readers):
            student = UserRule().user
            db_session.add(UserCohortMap(user=student, cohort=self.cohort))
            for _ in range(sessions_each):
                db_session.add(
                    UserReadingSession(student.id, self.article.id, datetime.now())
                )
        db_session.commit()

    def _teachers_and_classes(self):
        totals = compute_platform_totals(db_session)
        return totals["teachers"], totals["classes"]

    def test_class_whose_students_read_counts(self):
        self._enrol(MIN_ACTIVE_STUDENTS)
        self.assertEqual((1, 1), self._teachers_and_classes())

    def test_owning_a_class_alone_does_not_count(self):
        self.assertEqual((0, 0), self._teachers_and_classes())

    def test_too_few_active_students_does_not_count(self):
        self._enrol(MIN_ACTIVE_STUDENTS - 1)
        self.assertEqual((0, 0), self._teachers_and_classes())

    def test_students_who_barely_read_do_not_count(self):
        self._enrol(MIN_ACTIVE_STUDENTS, sessions_each=MIN_READING_SESSIONS - 1)
        self.assertEqual((0, 0), self._teachers_and_classes())

    def test_dev_accounts_are_not_teachers(self):
        self._enrol(MIN_ACTIVE_STUDENTS)
        self.teacher.is_dev = True
        db_session.commit()
        self.assertEqual((0, 0), self._teachers_and_classes())

    def test_cohort_of_teachers_is_not_a_class(self):
        self._enrol(MIN_ACTIVE_STUDENTS)
        self.cohort.is_cohort_of_teachers = True
        db_session.commit()
        self.assertEqual((0, 0), self._teachers_and_classes())

    def test_study_is_not_a_class(self):
        self._enrol(MIN_ACTIVE_STUDENTS)
        self.cohort.is_study = True
        db_session.commit()
        self.assertEqual((0, 0), self._teachers_and_classes())
