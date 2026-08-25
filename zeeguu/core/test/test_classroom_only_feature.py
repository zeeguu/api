from unittest import TestCase

import zeeguu.core
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.cohort_rule import CohortRule
from zeeguu.core.model.teacher import Teacher
from zeeguu.core.user_feature_toggles import is_feature_enabled_for_user

db_session = zeeguu.core.model.db.session


class ClassroomOnlyFeatureTest(ModelTestMixIn, TestCase):
    """Cohort.only_classroom_texts drives the classroom_only feature."""

    def setUp(self):
        super().setUp()
        self.cohort_rule = CohortRule()
        self.cohort = self.cohort_rule.cohort
        self.teacher = self.cohort_rule.teacher
        self.student = self.cohort_rule.student1
        self.student.add_user_to_cohort(self.cohort, db_session)

    def _classroom_only_for(self, user):
        return is_feature_enabled_for_user("classroom_only", user)

    def test_off_by_default(self):
        self.assertFalse(self._classroom_only_for(self.student))

    def test_on_when_the_cohort_asks_for_it(self):
        self.cohort.only_classroom_texts = True
        db_session.commit()

        self.assertTrue(self._classroom_only_for(self.student))

    def test_strictest_cohort_wins(self):
        self.cohort.only_classroom_texts = True
        unrestricted_cohort = CohortRule().cohort
        self.student.add_user_to_cohort(unrestricted_cohort, db_session)
        db_session.commit()

        self.assertTrue(self._classroom_only_for(self.student))

    def test_teachers_are_never_restricted(self):
        # A teacher needs the feed and the search to find texts to share.
        # CohortRule only links the teacher to the cohort; the Teacher row is
        # what User.isTeacher() actually looks at, and account creation is what
        # writes it in production.
        db_session.add(Teacher(self.teacher))
        self.cohort.only_classroom_texts = True
        self.teacher.add_user_to_cohort(self.cohort, db_session)
        db_session.commit()

        self.assertFalse(self._classroom_only_for(self.teacher))
