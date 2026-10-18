"""Which of a learner's words an audio lesson may pick."""
from datetime import datetime
from unittest import TestCase

import zeeguu.core
from zeeguu.core.audio_lessons.word_selector import select_words_for_audio_lesson
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.bookmark_rule import BookmarkRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord

session = zeeguu.core.model.db.session


class AudioWordSelectionTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.user_word = BookmarkRule(self.user).bookmark.user_word
        self.user_word.fit_for_study = True
        self.language = self.user_word.meaning.origin.language
        session.add(self.user_word)
        session.commit()

    def _selected(self):
        return select_words_for_audio_lesson(
            self.user, num_words=1, language=self.language, log_enabled=False
        )

    def _invalidate(self):
        # Invalid for the meaning, while this learner's word stays fit for
        # study: how another learner's validation leaves it.
        self.user_word.meaning.validated = Meaning.INVALID
        session.add(self.user_word.meaning)
        session.commit()

    def test_an_unscheduled_word_on_an_invalid_meaning_is_skipped(self):
        self.assertEqual(self._selected(), [self.user_word])
        self._invalidate()
        self.assertEqual(self._selected(), [])

    def test_a_scheduled_word_on_an_invalid_meaning_is_skipped(self):
        FourLevelsPerWord.find_or_create(session, self.user_word)
        session.commit()
        self.assertEqual(self._selected(), [self.user_word])
        self._invalidate()
        self.assertEqual(self._selected(), [])

    def test_a_recently_learned_word_on_an_invalid_meaning_is_skipped(self):
        self.user_word.learned_time = datetime.now()
        session.add(self.user_word)
        session.commit()
        self.assertEqual(self._selected(), [self.user_word])
        self._invalidate()
        self.assertEqual(self._selected(), [])
