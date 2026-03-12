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

   def test_update_friend_streak_multiple_friends(self):
      from zeeguu.core.model.language import Language
      from zeeguu.core.model.user_language import UserLanguage
      from zeeguu.core.model.friend import Friend

      # Create a language
      lang = Language.find_or_create("en")

      # Create three users
      user1 = self.user
      user2 = UserRule().user
      user3 = UserRule().user

      # Set up friendships: user1 ↔ user2, user1 ↔ user3
      friendship1 = Friend(user_id=user1.id, friend_id=user2.id)
      friendship2 = Friend(user_id=user1.id, friend_id=user3.id)
      session.add(friendship1)
      session.add(friendship2)
      session.commit()

      # Practice today for user1, user2, user3
      now = datetime.now()
      ul1 = UserLanguage.find_or_create(session, user1, lang)
      ul2 = UserLanguage.find_or_create(session, user2, lang)
      ul3 = UserLanguage.find_or_create(session, user3, lang)
      ul1.last_practiced = now
      ul2.last_practiced = now
      ul3.last_practiced = now
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
   def test_update_friend_streak_resets_to_one_without_user_languages(self):
      self.friendship.friend_streak = 7
      session.add(self.friendship)
      session.commit()

      self.friendship.update_friend_streak()

      assert self.friendship.friend_streak == 1

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

   def test_update_friend_streak_twice_only_increase_by_one(self):
      self._set_last_practiced(self.user, datetime.now())
      self._set_last_practiced(self.friend_user, datetime.now() - timedelta(days=1))

      self.friendship.update_friend_streak()
      self.friendship.update_friend_streak()

      assert self.friendship.friend_streak == 1

   def test_update_friend_streak_resets_when_one_friend_does_not_practice(self):
      # Start from an active streak to verify reset behavior.
      self.friendship.friend_streak = 4
      session.add(self.friendship)
      session.commit()

      self._set_last_practiced(self.user, datetime.now())
      self._set_last_practiced(self.friend_user, datetime.now() - timedelta(days=2))

      self.friendship.update_friend_streak()

      assert self.friendship.friend_streak == 1
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
      user_lang.last_practiced = datetime.now()
      friend_lang.last_practiced = datetime.now()
      session.add(user_lang)
      session.add(friend_lang)
      session.commit()

      # Add practice in a non-learned language (should not affect streak)
      user_lang_other = UserLanguage.find_or_create(session, self.user, lang2)
      friend_lang_other = UserLanguage.find_or_create(session, self.friend_user, lang1)
      user_lang_other.last_practiced = datetime.now() - timedelta(days=5)
      friend_lang_other.last_practiced = datetime.now() - timedelta(days=5)
      session.add(user_lang_other)
      session.add(friend_lang_other)
      session.commit()

      # Act: update streak
      self.friendship.update_friend_streak()

      # Assert: streak is 1, only learned_language practice is counted
      assert self.friendship.friend_streak == 1

