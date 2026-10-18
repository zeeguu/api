"""
Level A0 and lessons that build on the learner's history.

See docs/future-work/a0-audio-lessons.md. A0 is stored as cefr_level 0, which
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


def test_the_pieces_of_a_word_being_built_up_are_not_words():
    script = """Man: Undskyld. [3 seconds]
Man: Skyld. [3 seconds]
Man: Und. [3 seconds]
Man: Undskyld. [3 seconds]
Woman: En kaffe. [3 seconds]
"""
    assert target_language_words(script) == Counter({"undskyld": 2, "en": 1, "kaffe": 1})


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
    # Heard in lesson 2 first (kroner, the more heard, before undskyld), then lesson 1 only.
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
