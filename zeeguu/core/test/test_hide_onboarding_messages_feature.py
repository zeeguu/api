from unittest import TestCase

import zeeguu.core
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.cohort_rule import CohortRule
from zeeguu.core.user_feature_toggles import is_feature_enabled_for_user

db_session = zeeguu.core.model.db.session


class HideOnboardingMessagesFeatureTest(ModelTestMixIn, TestCase):
    """Students in the group2 study classes get hide_onboarding_messages."""

    def setUp(self):
        super().setUp()
        self.cohort_rule = CohortRule()
        self.cohort = self.cohort_rule.cohort
        self.student = self.cohort_rule.student1
        self.student.add_user_to_cohort(self.cohort, db_session)

    def _hidden_for(self, user):
        return is_feature_enabled_for_user("hide_onboarding_messages", user)

    def test_student_in_study_class_gets_feature(self):
        self.cohort.inv_code = "Group2S"
        db_session.commit()

        self.assertTrue(self._hidden_for(self.student))

    def test_student_in_other_class_does_not(self):
        self.assertFalse(self._hidden_for(self.student))
