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

    def _refuse(self, prompt_version, teacher_language_id=None):
        from zeeguu.core.model.audio_lesson_refusal import AudioLessonRefusal

        AudioLessonRefusal.record(
            session, self.user_word.meaning_id, teacher_language_id or self.user.native_language_id,
            prompt_version, AudioLessonRefusal.NOT_CORRECT, "test",
        )
        session.commit()

    def test_a_refusal_in_another_teacher_language_counts_too(self):
        # The precompute records the meaning's translation language, which can
        # differ from the learner's native language
        from zeeguu.core.audio_lessons.script_generator import MEANING_LESSON_PROMPT_VERSION

        other = self.user_word.meaning.translation.language_id
        if other == self.user.native_language_id:
            other = self.language.id
        self._refuse(MEANING_LESSON_PROMPT_VERSION, teacher_language_id=other)
        self.assertEqual(self._selected(), [])

    def test_recording_the_same_refusal_twice_keeps_one(self):
        from zeeguu.core.audio_lessons.script_generator import MEANING_LESSON_PROMPT_VERSION
        from zeeguu.core.model.audio_lesson_refusal import AudioLessonRefusal

        self._refuse(MEANING_LESSON_PROMPT_VERSION)
        self._refuse(MEANING_LESSON_PROMPT_VERSION)
        self.assertEqual(AudioLessonRefusal.query.count(), 1)

    def test_a_word_refused_under_the_current_prompt_is_skipped(self):
        from zeeguu.core.audio_lessons.script_generator import MEANING_LESSON_PROMPT_VERSION

        self._refuse(MEANING_LESSON_PROMPT_VERSION)
        self.assertEqual(self._selected(), [])

    def test_a_word_refused_under_an_older_prompt_is_tried_again(self):
        self._refuse("meaning_lesson-v5")
        self.assertEqual(self._selected(), [self.user_word])
