"""
The words an A0 lesson taught the learner to say go on their study list once
they have heard the lesson. See zeeguu/core/audio_lessons/lesson_words.py.

Against the real test database and the (fake) tokenizer: the helpers commit as
they go, which a stand-in session would hide.
"""

from types import SimpleNamespace

import pytest

from zeeguu.core.audio_lessons import lesson_words
from zeeguu.core.model import db
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson
from zeeguu.core.model.language import Language
from zeeguu.core.model.user_word import UserWord
from zeeguu.core.model.user_word_interaction_history import UserWordInteractionHistory
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule

SCRIPT = "Woman: Hej! Hvad vil du have? [1 seconds]\nMan: En kaffe, tak. [1 seconds]"


class _Llm:
    def __init__(self, answer):
        self.answer = answer

    def generate_text(self, *args, **kwargs):
        return self.answer


def _answering(monkeypatch, answer):
    import zeeguu.core.llm_services.llm_service as llm_service

    monkeypatch.setattr(llm_service, "get_llm_service", lambda *a, **k: _Llm(answer))


_FAKE = SimpleNamespace(
    id=1, script=SCRIPT, language=SimpleNamespace(code="da"), teacher_language=SimpleNamespace(code="en")
)


def test_reads_the_list_even_after_a_bracket_in_the_prose(monkeypatch):
    _answering(
        monkeypatch,
        'The words said [slow] and asked for:\n[{"word": "kaffe", "translation": "coffee", "sentence": "En kaffe, tak."},'
        ' {"word": "tak", "translation": "thank you"}]',
    )
    assert lesson_words.words_taught_to_say(_FAKE) == [
        ("kaffe", "coffee", "En kaffe, tak."),
        ("tak", "thank you", "tak"),
    ]


def test_an_empty_list_in_the_prose_is_not_the_answer(monkeypatch):
    _answering(monkeypatch, 'Not counted: [] -- the words: [{"word": "tak", "translation": "thank you"}]')
    assert lesson_words.words_taught_to_say(_FAKE) == [("tak", "thank you", "tak")]


def test_a_missing_translation_is_not_the_word_none(monkeypatch):
    _answering(monkeypatch, '[{"word": "hej", "translation": null, "sentence": null}]')
    assert lesson_words.words_taught_to_say(_FAKE) == []


def test_an_unreadable_answer_is_a_failure_not_an_empty_list(monkeypatch):
    # An empty list would count as done, and the lesson would never be tried again.
    _answering(monkeypatch, "[not json")
    with pytest.raises(lesson_words.UnreadableAnswer):
        lesson_words.words_taught_to_say(_FAKE)


class LessonWordsTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.da = Language.find_or_create("da")
        self.en = Language.find_or_create("en")
        self.dialogue = AudioLessonDialogue(
            SCRIPT, "café", "situation", self.da, teacher_language=self.en, builds_on_history=True
        )
        db.session.add(self.dialogue)
        db.session.commit()
        self.monkeypatch = pytest.MonkeyPatch()

    def tearDown(self):
        self.monkeypatch.undo()
        super().tearDown()

    def _taught(self, words):
        self.monkeypatch.setattr(lesson_words, "words_taught_to_say", lambda dialogue: words)

    def _user_words(self):
        return {
            uw.meaning.origin.content: uw for uw in UserWord.query.filter_by(user=self.user).all()
        }

    def test_all_the_words_are_scheduled_not_just_the_first(self):
        self._taught(
            [
                ("kaffe", "coffee", "En kaffe, tak."),
                ("hej", "hello", "En kaffe, tak."),  # not in its line: tried on its own
                ("tak", "thank you", "En kaffe, tak."),
            ]
        )
        added = lesson_words.schedule_words_from_lesson(db.session, self.user, self.dialogue)

        assert added == 3
        words = self._user_words()
        assert set(words) == {"kaffe", "hej", "tak"}
        assert words["hej"].preferred_bookmark.context.get_content() == "hej"
        assert words["kaffe"].preferred_bookmark.context.get_content() == "En kaffe, tak."
        for user_word in words.values():
            assert user_word.level == 1 and user_word.fit_for_study
            assert not user_word.is_user_added
            interactions = {
                i.interaction_type
                for i in UserWordInteractionHistory.query.filter_by(user_word=user_word).all()
            }
            # (Bookmark.find_or_create also logs "translated", for typed-in words too.)
            assert UserWordInteractionHistory.AUDIO_LESSON in interactions
            assert UserWordInteractionHistory.MANUAL_ADDITION not in interactions

    def test_a_word_the_learner_already_has_is_left_alone(self):
        from zeeguu.core.bookmark_operations.add_word_to_study import add_word_to_study

        _, kaffe, _ = add_word_to_study(db.session, self.user, "kaffe", "coffee", "da", "en", "En kaffe, tak.")
        kaffe.level = 3
        db.session.commit()

        self._taught([("kaffe", "coffee", "En kaffe, tak."), ("tak", "thank you", "En kaffe, tak.")])
        added = lesson_words.schedule_words_from_lesson(db.session, self.user, self.dialogue)

        assert added == 1
        assert self._user_words()["kaffe"].level == 3

    def test_completing_the_lesson_schedules_its_words(self):
        # run_in_background runs inline under app.testing.
        from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator

        lesson = DailyAudioLesson(
            user=self.user, created_by="test", duration_seconds=600, language=self.da, lesson_type="situation"
        )
        lesson.add_dialogue_segment(audio_lesson_dialogue=self.dialogue, sequence_order=1)
        db.session.add(lesson)
        db.session.commit()

        self._taught([("kaffe", "coffee", "En kaffe, tak.")])
        result = DailyLessonGenerator().update_lesson_state_for_user(
            self.user, lesson.id, {"action": "complete"}
        )

        assert result.get("is_completed")
        assert set(self._user_words()) == {"kaffe"}

    def test_a_word_looked_up_but_never_studied_is_scheduled(self):
        from zeeguu.core.model.meaning import Meaning
        from zeeguu.core.word_scheduling import BasicSRSchedule

        meaning = Meaning.find_or_create(db.session, "tak", "da", "thank you", "en", user=self.user)
        looked_up = UserWord.find_or_create(db.session, self.user, meaning)
        assert not BasicSRSchedule.find(looked_up)

        self._taught([("tak", "thank you", "En kaffe, tak.")])
        assert lesson_words.schedule_words_from_lesson(db.session, self.user, self.dialogue) == 1
        assert BasicSRSchedule.find(self._user_words()["tak"])

    def _lesson(self, dialogue=None):
        lesson = DailyAudioLesson(
            user=self.user, created_by="test", duration_seconds=600, language=self.da, lesson_type="situation"
        )
        lesson.add_dialogue_segment(audio_lesson_dialogue=dialogue or self.dialogue, sequence_order=1)
        db.session.add(lesson)
        db.session.commit()
        return lesson

    def _complete(self, lesson):
        from zeeguu.core.audio_lessons.daily_lesson_generator import DailyLessonGenerator

        return DailyLessonGenerator().update_lesson_state_for_user(self.user, lesson.id, {"action": "complete"})

    def _counting_model_calls(self, words):
        calls = []

        def taught(dialogue):
            calls.append(dialogue.id)
            return words

        self.monkeypatch.setattr(lesson_words, "words_taught_to_say", taught)
        return calls

    def test_completing_again_does_not_schedule_again(self):
        calls = self._counting_model_calls([("kaffe", "coffee", "En kaffe, tak.")])
        lesson = self._lesson()
        self._complete(lesson)
        self._complete(lesson)

        assert calls == [self.dialogue.id]
        assert db.session.get(DailyAudioLesson, lesson.id).words_scheduled_at is not None

    def test_a_lesson_another_run_has_claimed_is_not_scheduled_twice(self):
        # Two "complete" requests at once: both start the job, one claims it.
        calls = self._counting_model_calls([("kaffe", "coffee", "En kaffe, tak.")])
        lesson = self._lesson()
        assert lesson_words._claim(lesson)
        assert not lesson_words._claim(lesson)

        lesson_words._schedule_words_of(self.user, lesson)
        assert calls == []

    def test_a_failed_run_is_tried_again_with_the_next_lesson(self):
        def failing(dialogue):
            raise lesson_words.UnreadableAnswer("no list")

        self.monkeypatch.setattr(lesson_words, "words_taught_to_say", failing)
        first = self._lesson()
        self._complete(first)
        assert db.session.get(DailyAudioLesson, first.id).words_scheduled_at is None
        assert self._user_words() == {}

        second_dialogue = AudioLessonDialogue(
            SCRIPT, "bakery", "situation", self.da, teacher_language=self.en, builds_on_history=True
        )
        db.session.add(second_dialogue)
        second = self._lesson(second_dialogue)
        calls = self._counting_model_calls([("kaffe", "coffee", "En kaffe, tak.")])
        self._complete(second)

        assert calls == [self.dialogue.id, second_dialogue.id]
        assert set(self._user_words()) == {"kaffe"}
        for lesson in (first, second):
            assert db.session.get(DailyAudioLesson, lesson.id).words_scheduled_at is not None

    def test_a_learned_word_or_a_choice_of_the_learner_is_left_alone(self):
        from datetime import datetime
        from zeeguu.core.model.study_choice import StudyChoice
        from zeeguu.core.model.meaning import Meaning

        learned = UserWord.find_or_create(
            db.session, self.user, Meaning.find_or_create(db.session, "kaffe", "da", "coffee", "en", user=self.user)
        )
        learned.learned_time = datetime.now()
        excluded = UserWord.find_or_create(
            db.session, self.user, Meaning.find_or_create(db.session, "tak", "da", "thank you", "en", user=self.user)
        )
        excluded.study_choice = StudyChoice.SKIP
        db.session.commit()

        self._taught([("kaffe", "coffee", "En kaffe, tak."), ("tak", "thank you", "En kaffe, tak.")])
        assert lesson_words.schedule_words_from_lesson(db.session, self.user, self.dialogue) == 0
        words = self._user_words()
        assert words["kaffe"].is_learned()
        assert words["tak"].study_choice == StudyChoice.SKIP

    def test_at_the_learners_limit_a_word_is_added_but_not_scheduled(self):
        from zeeguu.core.model.user_preference import UserPreference
        from zeeguu.core.word_scheduling import BasicSRSchedule

        UserPreference.set(db.session, self.user, UserPreference.MAX_WORDS_TO_SCHEDULE, "1")
        self._taught([("kaffe", "coffee", "En kaffe, tak."), ("tak", "thank you", "En kaffe, tak.")])
        assert lesson_words.schedule_words_from_lesson(db.session, self.user, self.dialogue) == 1
        words = self._user_words()
        assert set(words) == {"kaffe", "tak"}
        assert sum(1 for w in words.values() if BasicSRSchedule.find(w)) == 1

    def test_a_word_a_lesson_taught_records_the_lesson_as_its_translator(self):
        # Not MANUAL: the translation came from the lesson's LLM, not the learner
        from zeeguu.core.model import TranslationService

        self._taught([("kaffe", "coffee", "En kaffe, tak.")])
        lesson_words.schedule_words_from_lesson(db.session, self.user, self.dialogue)

        bookmark = self._user_words()["kaffe"].preferred_bookmark
        assert bookmark.translation_service.name == TranslationService.AUDIO_LESSON
