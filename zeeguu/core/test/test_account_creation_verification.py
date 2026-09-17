from unittest import TestCase

import zeeguu.core
from zeeguu.core.account_management.user_account_creation import create_account
from zeeguu.core.model.unique_code import UniqueCode
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.cohort_rule import CohortRule

db_session = zeeguu.core.model.db.session


class AccountCreationVerificationTest(ModelTestMixIn, TestCase):
    """
    A signup that carries a teacher's invitation code is vouched for by that
    teacher, so it skips email verification. Everyone else still confirms.
    """

    def setUp(self):
        super().setUp()
        self.cohort = CohortRule().cohort
        self.cohort.inv_code = "a-real-class"
        db_session.add(self.cohort)
        db_session.commit()

    def _signup(self, email, invite_code):
        return create_account(
            db_session,
            username="A Student",
            password="secret",
            invite_code=invite_code,
            email=email,
            learned_language_code="de",
            native_language_code="nl",
            learned_cefr_level="1",
        )

    def test_cohort_signup_is_verified_without_email(self):
        user = self._signup("student@school.example", "a-real-class")

        self.assertTrue(user.email_verified)
        # No code is issued, so nothing invites them to hunt for a step that
        # isn't there.
        self.assertIsNone(UniqueCode.find_last_code(user.email))

    def test_cohort_match_is_case_insensitive(self):
        user = self._signup("shouty@school.example", "A-REAL-CLASS")

        self.assertTrue(user.email_verified)

    def test_signup_without_an_invite_code_still_verifies_by_email(self):
        user = self._signup("individual@example.com", "")

        self.assertFalse(user.email_verified)
        self.assertIsNotNone(UniqueCode.find_last_code(user.email))

    def test_invite_code_matching_no_cohort_still_verifies_by_email(self):
        # valid_invite_code also accepts the global INVITATION_CODES from
        # config. Those belong to no class, so nobody has vouched for the
        # person using one and they must confirm their address like anyone else.
        user = self._signup("nocohort@example.com", "not-a-class-code")

        self.assertFalse(user.email_verified)
        self.assertIsNotNone(UniqueCode.find_last_code(user.email))

    def test_the_avatar_is_committed_on_a_cohort_signup(self):
        # The avatar used to ride along on the verification code's commit, and
        # that commit is now skipped for cohort signups. Roll back before
        # asserting: anything merely pending in the session is discarded, so
        # only a genuinely committed avatar survives. (Querying without the
        # rollback would autoflush and pass either way.)
        from zeeguu.core.model.user_avatar import UserAvatar

        user_id = self._signup("avatar@school.example", "a-real-class").id
        db_session.rollback()

        self.assertIsNotNone(UserAvatar.find(user_id))
