"""An unset word scheduling strategy depends on when the account was made:
frequency_priority from FREQUENCY_PRIORITY_DEFAULT_FROM on, first_come before."""

from datetime import timedelta

from zeeguu.core.model import UserPreference
from zeeguu.core.model.db import db
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule

db_session = db.session
CUTOFF = UserPreference.FREQUENCY_PRIORITY_DEFAULT_FROM


class WordSchedulingStrategyDefaultTest(ModelTestMixIn):
    def _user_created_at(self, created_at):
        user = UserRule().user
        user.created_at = created_at
        db_session.add(user)
        db_session.commit()
        return user

    def test_a_new_account_gets_frequency_priority(self):
        user = self._user_created_at(CUTOFF)
        assert UserPreference.get_word_scheduling_strategy(user) == UserPreference.FREQUENCY_PRIORITY

    def test_an_older_account_keeps_first_come(self):
        user = self._user_created_at(CUTOFF - timedelta(seconds=1))
        assert UserPreference.get_word_scheduling_strategy(user) == UserPreference.FIRST_COME

    def test_an_account_without_a_creation_date_keeps_first_come(self):
        user = self._user_created_at(None)
        assert UserPreference.get_word_scheduling_strategy(user) == UserPreference.FIRST_COME

    def test_a_stored_choice_wins_over_the_default(self):
        user = self._user_created_at(CUTOFF)
        pref = UserPreference.find_or_create(
            db_session, user, UserPreference.WORD_SCHEDULING_STRATEGY
        )
        pref.value = UserPreference.FIRST_COME
        db_session.add(pref)
        db_session.commit()
        assert UserPreference.get_word_scheduling_strategy(user) == UserPreference.FIRST_COME

    def test_the_listing_shows_the_strategy_in_use(self):
        old = self._user_created_at(CUTOFF - timedelta(days=30))
        new = self._user_created_at(CUTOFF)
        assert UserPreference.all_for_user(old)["word_scheduling_strategy"] == "first_come"
        assert UserPreference.all_for_user(new)["word_scheduling_strategy"] == "frequency_priority"
