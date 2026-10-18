"""
Level A0 and lessons that build on the learner's history.

Design: future-work/a0-audio-lessons.md in the docs repo. A0 is stored as cefr_level 0, which
used to be the "not set" default and read as C2; not set is now NULL.
"""

from collections import Counter

import pytest

from zeeguu.core.audio_lessons.words_heard import (
    HeardLesson,
    history_table,
    target_language_words,
)
from zeeguu.core.model import db
from zeeguu.core.model.audio_lesson_dialogue import AudioLessonDialogue
from zeeguu.core.model.user_language import UserLanguage
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.user_rule import UserRule


SCRIPT = """Teacher: Listen to this conversation. [0.5 seconds]
Man: Undskyld. [1 seconds]
Woman: Ja? [1 seconds]
Man: Forstår du engelsk? [1 seconds]
Teacher: How do you say "excuse me"? [5 seconds]
TeacherL2: Undskyld [3 seconds]
Man: Undskyld. [3 seconds]
"""


def test_counts_only_what_the_target_language_voices_say():
    words = target_language_words(SCRIPT)
    assert words == Counter({"undskyld": 3, "ja": 1, "forstår": 1, "du": 1, "engelsk": 1})
    # The Teacher's English never counts, nor do the timing markers.
    assert "listen" not in words and "seconds" not in words


def test_a_slow_line_is_marked_and_the_marker_is_not_text():
    from zeeguu.core.audio_lessons.script_parser import parse_script

    script = "Woman: Kaffe. [slow] [3 seconds]\nWoman: Kaffe. [3 seconds]\n"
    assert parse_script(script, with_speed=True) == [
        ("woman", "Kaffe.", 3.0, True),
        ("woman", "Kaffe.", 3.0, False),
    ]
    assert parse_script(script) == [("woman", "Kaffe.", 3.0), ("woman", "Kaffe.", 3.0)]
    assert target_language_words(script) == Counter({"kaffe": 2})


def test_a_slow_marker_on_its_own_line_slows_nobody():
    from zeeguu.core.audio_lessons.script_parser import parse_script

    script = "Teacher: Listen. [1 seconds]\n[slow]\nWoman: Kaffe. [3 seconds]\n"
    assert parse_script(script, with_speed=True) == [
        ("teacher", "Listen.", 1.0, False),
        ("woman", "Kaffe.", 3.0, False),
    ]


def test_a_short_word_inside_a_longer_one_still_counts():
    # "ja" said once, inside "jakke" said often: it was heard, and stays.
    script = "Woman: Ja. [1 seconds]\nMan: En jakke. [1 seconds]\nMan: En jakke. [1 seconds]\n"
    assert target_language_words(script)["ja"] == 1


def test_history_table_puts_the_most_recent_words_first():
    heard = [
        HeardLesson("At the café", Counter({"undskyld": 14, "kaffe": 2})),
        HeardLesson("In the shop", Counter({"undskyld": 3, "kroner": 9})),
    ]
    table = history_table(heard)
    lines = table.splitlines()
    assert lines[0] == "Lesson 1: At the café"
    assert lines[1] == "Lesson 2: In the shop"
    rows = [line.split()[0] for line in lines[4:]]
    # Words of the latest lesson first, those most heard overall before the
    # others (undskyld 17 before kroner 9), then words of lesson 1 only.
    assert rows == ["undskyld", "kroner", "kaffe"]
    assert "2 (3), 1 (14)" in table


def test_no_history_is_an_empty_table():
    assert history_table([]) == ""


class LevelTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.ul = UserLanguage.find_or_create(db.session, self.user, self.user.learned_language)

    def _level(self, stored):
        self.ul.cefr_level = stored
        db.session.add(self.ul)
        db.session.commit()

    def test_a0_is_a0_for_audio_and_a1_for_reading(self):
        self._level(0)
        assert self.user.audio_lesson_level_for_learned_language() == "A0"
        assert self.user.cefr_level_for_learned_language() == "A1"

    def test_other_levels_unchanged(self):
        self._level(3)
        assert self.user.audio_lesson_level_for_learned_language() == "B1"
        assert self.user.cefr_level_for_learned_language() == "B1"

    def test_unset_is_not_c2(self):
        self._level(None)
        assert self.user.audio_lesson_level_for_learned_language() == "A1"
        with pytest.raises(ValueError):
            self.user.cefr_level_for_learned_language()

    def test_new_user_language_has_no_level(self):
        other = UserLanguage(self.user, self.user.native_language)
        assert other.cefr_level is None

    def test_a0_is_saved_when_switching_language(self):
        # The reason for parse_cefr_level: 0 is falsy, and `if cefr_level:` dropped it.
        self._level(3)
        self.user.set_learned_language(self.user.learned_language.code, "0", db.session)
        assert self.user.audio_lesson_level_for_learned_language() == "A0"

    def test_a_bad_level_changes_nothing(self):
        self._level(3)
        with pytest.raises(ValueError):
            self.user.set_learned_language(self.user.learned_language.code, "7", db.session)
        assert self.user.audio_lesson_level_for_learned_language() == "B1"

    def test_no_level_given_leaves_the_level_alone(self):
        self._level(3)
        self.user.set_learned_language(self.user.learned_language.code, "", db.session)
        assert self.user.audio_lesson_level_for_learned_language() == "B1"

    def test_an_unusable_level_falls_back_to_a1_for_audio(self):
        self._level(7)
        assert self.user.audio_lesson_level_for_learned_language() == "A1"
        with pytest.raises(ValueError):
            self.user.cefr_level_for_learned_language()

    def test_parse_cefr_level(self):
        assert UserLanguage.parse_cefr_level(None) is None
        assert UserLanguage.parse_cefr_level("") is None
        assert UserLanguage.parse_cefr_level("0") == 0
        assert UserLanguage.parse_cefr_level(6) == 6
        with pytest.raises(ValueError):
            UserLanguage.parse_cefr_level("7")


def test_a_lesson_built_on_history_cannot_be_general():
    class _Lang:
        id = 1

    with pytest.raises(AssertionError):
        AudioLessonDialogue("s", "café", "situation", _Lang(), is_general=True, builds_on_history=True)


class AudioLessonCharacterTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user

    def test_unset_and_either_mean_alternate(self):
        from zeeguu.core.model.user_preference import UserPreference

        assert UserPreference.get_audio_lesson_character(self.user) is None
        UserPreference.set(db.session, self.user, UserPreference.AUDIO_LESSON_CHARACTER, "either")
        assert UserPreference.get_audio_lesson_character(self.user) is None

    def test_a_chosen_character_is_kept(self):
        from zeeguu.core.model.user_preference import UserPreference

        UserPreference.set(db.session, self.user, UserPreference.AUDIO_LESSON_CHARACTER, "woman")
        assert UserPreference.get_audio_lesson_character(self.user) == "woman"


def test_a0_builds_on_history_and_has_no_word_lessons():
    from zeeguu.core.audio_lessons.script_generator import builds_on_history, word_lesson_level

    assert builds_on_history("A0") and not builds_on_history("A1")
    # Word lessons are cached and shared by word: there is no A0 version.
    assert word_lesson_level("A0") == "A1"
    assert word_lesson_level("B2") == "B2"


class HistoryTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.language = self.user.learned_language

    def _lesson(self, script, builds_on_history, completed):
        from zeeguu.core.model.daily_audio_lesson import DailyAudioLesson

        dialogue = AudioLessonDialogue(
            script, "café", "situation", self.language, builds_on_history=builds_on_history
        )
        db.session.add(dialogue)
        lesson = DailyAudioLesson(
            user=self.user, created_by="test", duration_seconds=600,
            language=self.language, lesson_type="situation",
        )
        lesson.add_dialogue_segment(audio_lesson_dialogue=dialogue, sequence_order=1)
        if completed:
            lesson.mark_completed()
        db.session.add(lesson)
        db.session.commit()

    def test_only_heard_lessons_built_on_history_count(self):
        from zeeguu.core.audio_lessons.words_heard import heard_lessons, history_lesson_count

        self._lesson("Man: En kaffe, tak. [1 seconds]", builds_on_history=True, completed=True)
        self._lesson("Man: Jeg forstår ikke. [1 seconds]", builds_on_history=True, completed=False)
        self._lesson("Man: Hvor er stationen? [1 seconds]", builds_on_history=False, completed=True)

        heard = heard_lessons(self.user, self.language)
        assert [set(h.words) for h in heard] == [{"en", "kaffe", "tak"}]
        # Roles alternate over every lesson of this kind, heard or not.
        assert history_lesson_count(self.user, self.language) == 2


def test_a_level_must_be_a_whole_number():
    with pytest.raises(ValueError):
        UserLanguage.parse_cefr_level(2.9)
    with pytest.raises(ValueError):
        UserLanguage.parse_cefr_level(False)
    assert UserLanguage.parse_cefr_level(2.0) == 2


def test_slow_beside_a_standalone_pause_slows_nobody():
    from zeeguu.core.audio_lessons.script_parser import parse_script

    script = "Teacher: Listen. [1 seconds]\n[slow] [3 seconds]\nWoman: Kaffe. [3 seconds]\n"
    assert parse_script(script, with_speed=True) == [
        ("teacher", "Listen.", 1.0, False),
        ("silence", "", 3.0, False),
        ("woman", "Kaffe.", 3.0, False),
    ]
