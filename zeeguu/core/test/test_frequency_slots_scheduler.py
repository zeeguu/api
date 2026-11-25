"""Frequency slots in the scheduler (preference frequent_words_first)."""

from zeeguu.core.model import UserPreference
from zeeguu.core.model.db import db
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord

db_session = db.session


class FrequencySlotsTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        UserPreference.find_or_create(
            db_session, self.user, UserPreference.MAX_WORDS_TO_SCHEDULE, "2"
        )
        self._set_frequent_words_first("true")

    def _set_frequent_words_first(self, value):
        pref = UserPreference.find_or_create(
            db_session, self.user, UserPreference.FREQUENT_WORDS_FIRST
        )
        pref.value = value
        db_session.add(pref)
        db_session.commit()

    def _user_word(self, rank, scheduled_at_level=None):
        user_word = BookmarkRule(self.user).bookmark.user_word
        user_word.fit_for_study = 1
        user_word.meaning.origin.rank = rank
        db_session.add(user_word)
        db_session.commit()
        if scheduled_at_level is not None:
            FourLevelsPerWord.find_or_create(db_session, user_word)
            user_word.level = scheduled_at_level
            db_session.add(user_word)
            db_session.commit()
        return user_word

    def _is_scheduled(self, user_word):
        return BasicSRSchedule.query.filter_by(user_word_id=user_word.id).first() is not None

    def test_a_more_frequent_word_takes_the_slot_of_a_rarer_one(self):
        rare = self._user_word(9_000, scheduled_at_level=1)
        kept = self._user_word(500, scheduled_at_level=1)
        frequent = self._user_word(1_000)

        BasicSRSchedule.give_slots_to_more_frequent_words(self.user)
        to_study = BasicSRSchedule.user_words_to_study(self.user)

        assert not self._is_scheduled(rare)
        assert rare.fit_for_study == 1
        assert self._is_scheduled(kept)
        assert frequent.id in [uw.id for uw in to_study]

    def test_a_word_at_level_2_keeps_its_slot(self):
        rare = self._user_word(9_000, scheduled_at_level=2)
        self._user_word(8_000, scheduled_at_level=2)
        self._user_word(1_000)

        BasicSRSchedule.give_slots_to_more_frequent_words(self.user)

        assert self._is_scheduled(rare)

    def test_no_swap_while_a_slot_is_free(self):
        rare = self._user_word(9_000, scheduled_at_level=1)
        self._user_word(1_000)

        BasicSRSchedule.give_slots_to_more_frequent_words(self.user)

        assert self._is_scheduled(rare)

    def test_with_the_preference_off_slots_are_kept(self):
        self._set_frequent_words_first("false")
        rare = self._user_word(9_000, scheduled_at_level=1)
        self._user_word(8_000, scheduled_at_level=1)
        self._user_word(1_000)

        BasicSRSchedule.give_slots_to_more_frequent_words(self.user)

        assert self._is_scheduled(rare)

    def test_listing_the_words_to_study_changes_no_slot(self):
        # the practice-count badge calls user_words_to_study: a count must not write
        rare = self._user_word(9_000, scheduled_at_level=1)
        self._user_word(8_000, scheduled_at_level=1)
        self._user_word(1_000)

        BasicSRSchedule.user_words_to_study(self.user)

        assert self._is_scheduled(rare)
