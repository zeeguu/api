from datetime import datetime, timedelta

import zeeguu.core
import zeeguu.core.friends.listeners  # noqa: F401
from zeeguu.core.friends.friend_streak import update_streak
from zeeguu.core.model.friendship import Friendship
from zeeguu.core.model.user import User
from zeeguu.core.model.user_language import UserLanguage
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class UserSearchTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()

        self.searching_user = UserRule().user

    def test_exact_username_match_is_ranked_first(self):
        UserRule().user.username = "bigjohn"
        UserRule().user.username = "johnny"
        exact = UserRule().user
        exact.username = "john"

        session.commit()

        results = User.search(self.searching_user.id, "john")

        users = [user for user, avatar in results]

        self.assertEqual(3, len(users))  # Ensure all three users are returned
        self.assertEqual(exact.id, users[0].id)

    def test_prefix_matches_are_ranked_before_contains_matches(self):
        contains = UserRule().user
        contains.username = "bigjohn"
        prefix = UserRule().user
        prefix.username = "johnny"

        session.commit()

        results = User.search(self.searching_user.id, "john")

        users = [user for user, avatar in results]

        self.assertEqual(2, len(users))  # Ensure all two users are returned
        self.assertLess(
            users.index(prefix),
            users.index(contains),
        )


    def test_shorter_prefix_matches_are_ranked_first(self):
        # Add longer first so that we can test that the shorter one is ranked first after search
        longer = UserRule().user
        longer.username = "john123456"
        shorter = UserRule().user
        shorter.username = "john1"

        session.commit()

        results = User.search(self.searching_user.id, "john")

        users = [user for user, avatar in results]

        self.assertEqual(2, len(users))  # Ensure all two users are returned
        self.assertLess(
            users.index(shorter),
            users.index(longer),
        )

    def test_shorter_prefix_matches_are_ranked_first_v2(self):
        longer = UserRule().user
        longer.username = "witty_beaver123456"
        shorter1 = UserRule().user
        shorter1.username = "witty_beaver1"
        shorter0 = UserRule().user
        shorter0.username = "witty_beaver0"


        session.commit()

        results = User.search(self.searching_user.id, "witty_beaver")

        users = [user for user, avatar in results]

        self.assertEqual(3, len(users))  # Ensure all three users are returned
        self.assertLess(
            users.index(shorter0),
            users.index(longer),
        )
        self.assertLess(
            users.index(shorter1),
            users.index(longer),
        )

        self.assertLess(
            users.index(shorter0),
            users.index(shorter1),
        )
        


    def test_current_user_is_not_returned(self):
        self.searching_user.username = "john"

        UserRule().user.username = "johnny"
        UserRule().user.username = "bigjohn"
        session.commit()

        results = User.search(self.searching_user.id, "john")

        users = [user for user, avatar in results]

        self.assertNotIn(self.searching_user.id, [u.id for u in users])
        self.assertEqual(2, len(users))  # Ensure only the other two users are returned