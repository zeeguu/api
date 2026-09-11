from datetime import datetime, time, timedelta

import zeeguu.core
import zeeguu.core.friends.listeners  # noqa: F401
from zeeguu.core.friends.friend_streak import update_streak
from zeeguu.core.model.friendship import Friendship
from zeeguu.core.model.user_language import UserLanguage
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.util.time import SERVER_TZ, user_local_today, user_zone

session = zeeguu.core.model.db.session


def practiced_days_ago(user, days=0):
   """
   A naive, server-frame timestamp that the code under test reads back as
   `days` days before *this user's* local today.

   The streak code never looks at a raw `last_practiced`: it runs the value
   through `to_user_local_date`, which stamps the naive column with SERVER_TZ
   and converts into the user's zone. So a test that stores a bare
   `datetime.now()` is writing the developer machine's wall clock into a column
   that is read as SERVER_TZ, and the two sides disagree about which day it is
   whenever those differ -- e.g. on a CEST machine between local midnight and
   UTC midnight, where the test means the 12th and the code reads the 11th.
   Building the timestamp in the user's frame and converting it into the
   server's keeps "today" and "yesterday" meaning the same thing to both,
   at every hour and in every user timezone.

   Noon local is used so the value stays a full half-day away from either
   midnight, and so no DST transition can move it onto a neighbouring date.
   """
   local_day = user_local_today(user) - timedelta(days=days)
   local_noon = datetime.combine(local_day, time(12, 0), tzinfo=user_zone(user))
   return local_noon.astimezone(SERVER_TZ).replace(tzinfo=None)


class FriendTest(ModelTestMixIn):
   def setUp(self):
      super().setUp()
      self.user = UserRule().user
      self.friend_user = UserRule().user
      self.friendship = Friendship(user_a_id=self.user.id, user_b_id=self.friend_user.id)
      session.add(self.friendship)
      session.commit()

   def _set_last_practiced(self, user, practiced_at):
      user_language = UserLanguage.find_or_create(session, user, user.learned_language)
      user_language.last_practiced = practiced_at
      session.add(user_language)
      session.commit()

   def test_update_friend_streak_multiple_friends(self):
      from zeeguu.core.model.language import Language
      from zeeguu.core.model.user_language import UserLanguage
      from zeeguu.core.model.friendship import Friendship

      # Create a language
      lang = Language.find_or_create("en")

      # Create three users
      user1 = self.user
      user2 = UserRule().user
      user3 = UserRule().user

      # Set up friendships: user1 ↔ user2, user1 ↔ user3
      friendship1 = Friendship(user_a_id=user1.id, user_b_id=user2.id)
      friendship2 = Friendship(user_a_id=user1.id, user_b_id=user3.id)
      session.add(friendship1)
      session.add(friendship2)
      session.commit()

      # Practice today for user1, user2, user3
      ul1 = UserLanguage.find_or_create(session, user1, lang)
      ul2 = UserLanguage.find_or_create(session, user2, lang)
      ul3 = UserLanguage.find_or_create(session, user3, lang)
      ul1.last_practiced = practiced_days_ago(user1, 1)
      ul2.last_practiced = practiced_days_ago(user2)
      ul3.last_practiced = practiced_days_ago(user3)
      session.add(ul1)
      session.add(ul2)
      session.add(ul3)
      session.commit()

      # Update streak for user1 (should update both friendships)
      ul1.update_streak_if_needed(user1, session)

      # Refresh friendships from DB
      session.refresh(friendship1)
      session.refresh(friendship2)

      assert friendship1.friend_streak == 1
      assert friendship2.friend_streak == 1

   def test_update_friend_streak_does_not_reset_without_user_languages(self):
      self.friendship.friend_streak = 7
      session.add(self.friendship)
      session.commit()

      update_streak(friendship=self.friendship)

      assert self.friendship.friend_streak == 7

   def test_update_friend_streak_sets_to_one_if_both_practiced_today(self):
      self._set_last_practiced(self.user, practiced_days_ago(self.user))
      self._set_last_practiced(self.friend_user, practiced_days_ago(self.friend_user))

      update_streak(friendship=self.friendship)

      assert self.friendship.friend_streak == 1

   def test_update_friend_streak_sets_to_one_if_only_one_practiced_today(self):
      self._set_last_practiced(self.user, practiced_days_ago(self.user))
      self._set_last_practiced(self.friend_user, practiced_days_ago(self.friend_user, 1))

      update_streak(friendship=self.friendship)

      assert self.friendship.friend_streak == 0

   def test_update_friend_streak_twice_only_increase_by_one(self):
      self._set_last_practiced(self.user, practiced_days_ago(self.user))
      self._set_last_practiced(self.friend_user, practiced_days_ago(self.friend_user, 1))

      update_streak(friendship=self.friendship)
      update_streak(friendship=self.friendship)

      assert self.friendship.friend_streak == 0

   def test_update_friend_streak_resets_when_one_friend_does_not_practice(self):
      # Start from an active streak to verify reset behavior.
      self.friendship.friend_streak = 4
      session.add(self.friendship)
      session.commit()

      self._set_last_practiced(self.user, practiced_days_ago(self.user))
      self._set_last_practiced(self.friend_user, practiced_days_ago(self.friend_user, 2))

      update_streak(friendship=self.friendship)

      assert self.friendship.friend_streak == 0
      assert self.friendship.friend_streak_last_updated is not None


   def test_update_friend_streak_uses_learned_language(self):
      # Setup: user and friend each have two languages, but only learned_language should count
      from zeeguu.core.model.language import Language

      # Create two languages
      lang1 = Language.find_or_create("en")
      lang2 = Language.find_or_create("de")

      # Assign learned_language for both users
      self.user.learned_language = lang1
      self.friend_user.learned_language = lang2
      session.add(self.user)
      session.add(self.friend_user)
      session.commit()

      # Practice in learned_language for both users
      user_lang = UserLanguage.find_or_create(session, self.user, lang1)
      friend_lang = UserLanguage.find_or_create(session, self.friend_user, lang2)
      user_lang.last_practiced = practiced_days_ago(self.user)
      friend_lang.last_practiced = practiced_days_ago(self.friend_user)
      session.add(user_lang)
      session.add(friend_lang)
      session.commit()

      # Add practice in a non-learned language (should not affect streak)
      user_lang_other = UserLanguage.find_or_create(session, self.user, lang2)
      friend_lang_other = UserLanguage.find_or_create(session, self.friend_user, lang1)
      user_lang_other.last_practiced = practiced_days_ago(self.user, 5)
      friend_lang_other.last_practiced = practiced_days_ago(self.friend_user, 5)
      session.add(user_lang_other)
      session.add(friend_lang_other)
      session.commit()

      # Act: update streak
      update_streak(friendship=self.friendship)

      # Assert: streak is 1, only learned_language practice is counted
      assert self.friendship.friend_streak == 1
