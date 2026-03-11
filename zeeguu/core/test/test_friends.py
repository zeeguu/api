from datetime import datetime, timedelta

import zeeguu.core
from zeeguu.core.model.friend import Friend
from zeeguu.core.model.user_language import UserLanguage
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule

session = zeeguu.core.model.db.session


class FriendTest(ModelTestMixIn):
   def setUp(self):
      super().setUp()
      self.user = UserRule().user
      self.friend_user = UserRule().user
      self.friendship = Friend(user_id=self.user.id, friend_id=self.friend_user.id)
      session.add(self.friendship)
      session.commit()

   def _set_last_practiced(self, user, practiced_at):
      user_language = UserLanguage.find_or_create(session, user, user.learned_language)
      user_language.last_practiced = practiced_at
      session.add(user_language)
      session.commit()

   def test_update_friend_streak_resets_to_zero_without_user_languages(self):
      self.friendship.friend_streak = 7
      session.add(self.friendship)
      session.commit()

      self.friendship.update_friend_streak()

      assert self.friendship.friend_streak == 0

   def test_update_friend_streak_sets_to_one_if_both_practiced_today(self):
      now = datetime.now()
      self._set_last_practiced(self.user, now)
      self._set_last_practiced(self.friend_user, now)

      self.friendship.update_friend_streak()

      assert self.friendship.friend_streak == 1

   def test_update_friend_streak_sets_to_one_if_only_one_practiced_today(self):
      self._set_last_practiced(self.user, datetime.now())
      self._set_last_practiced(self.friend_user, datetime.now() - timedelta(days=1))

      self.friendship.update_friend_streak()

      assert self.friendship.friend_streak == 1

   def test_update_friend_streak_sets_to_one_if_only_one_practiced_today(self):
      self._set_last_practiced(self.user, datetime.now())
      self._set_last_practiced(self.friend_user, datetime.now() - timedelta(days=1))

      self.friendship.update_friend_streak()
      self.friendship.update_friend_streak()

      assert self.friendship.friend_streak == 1

