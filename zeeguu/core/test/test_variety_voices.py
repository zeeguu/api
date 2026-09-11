from unittest import TestCase

import zeeguu.core
from zeeguu.core.audio_lessons.voice_config import (
    DEFAULT_LOCALE,
    VOICE_CONFIG,
    countries_with_voices,
    get_voice_id,
    has_voice,
    locale_for,
    voice_catalogue,
)
from zeeguu.core.language.varieties import varieties_for
from zeeguu.core.model import AudioLessonMeaning, Language, User, UserLanguage
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.meaning_rule import MeaningRule
from zeeguu.core.test.rules.user_rule import UserRule

db_session = zeeguu.core.model.db.session


class LocaleMapTest(TestCase):
    """
    Which locale a language is read in. The map used to be derived by splitting
    the VOICE_CONFIG keys on "-", which these tests exist to stop coming back:
    a second locale for a language made the winner a function of dict order.
    """

    def test_a_second_locale_does_not_disturb_the_default(self):
        assert "nl-BE" in VOICE_CONFIG and "pt-BR" in VOICE_CONFIG
        assert locale_for("nl") == "nl-NL"
        assert locale_for("pt") == "pt-PT"

    def test_a_variety_is_read_in_its_own_locale(self):
        assert locale_for("nl", "BE") == "nl-BE"
        assert locale_for("pt", "BR") == "pt-BR"

    def test_a_variety_with_no_voice_falls_back_rather_than_failing(self):
        # Google has no Belgian French voice at all, so the only alternatives a
        # Walloon learner has are the French of France or silence.
        assert not has_voice("fr", "BE")
        assert locale_for("fr", "BE") == "fr-FR"

    def test_a_full_locale_is_left_alone(self):
        # The teacher voice is asked for as 'en-US', not as a language plus variety.
        assert locale_for("en-US") == "en-US"

    def test_every_default_names_a_locale_that_exists(self):
        for language_code, locale in DEFAULT_LOCALE.items():
            assert locale in VOICE_CONFIG, f"{language_code} defaults to a missing {locale}"

    def test_every_configured_locale_belongs_to_a_language_with_a_default(self):
        # Otherwise the locale is unreachable: nothing would ever resolve to it.
        for locale in VOICE_CONFIG:
            assert locale.split("-")[0] in DEFAULT_LOCALE

    def test_an_unknown_language_is_refused(self):
        try:
            locale_for("zz")
            assert False, "zz is not a language with voices"
        except ValueError:
            pass

    def test_the_voice_id_follows_the_variety(self):
        assert get_voice_id("nl", "woman").startswith("nl-NL")
        assert get_voice_id("nl", "woman", "BE").startswith("nl-BE")


class VoiceAvailabilityTest(TestCase):
    """
    What a voice control may offer. Derived from the voices rather than from the
    catalogue of varieties, so it cannot offer an accent nobody can be read in.
    """

    def test_a_language_whose_varieties_both_have_voices_offers_both(self):
        assert countries_with_voices("nl") == ("NL", "BE")
        assert countries_with_voices("pt") == ("PT", "BR")

    def test_a_single_remaining_option_is_no_control_at_all(self):
        # French has two varieties and one voice. Offering that one asks the
        # learner to make a choice that has already been made for them.
        assert varieties_for("fr") == ("FR", "BE")
        assert countries_with_voices("fr") == ()

    def test_a_language_with_no_varieties_offers_nothing(self):
        assert countries_with_voices("da") == ()

    def test_the_catalogue_carries_only_languages_with_a_real_choice(self):
        catalogue = voice_catalogue()

        assert "fr" not in catalogue and "da" not in catalogue
        assert catalogue["nl"] == [
            dict(country="NL", name="Dutch from the Netherlands"),
            dict(country="BE", name="Belgian Dutch"),
        ]


class ValidatedVoiceVarietyTest(TestCase):
    def test_a_voice_variety_is_stored_uppercased(self):
        assert User.validated_voice_variety("nl", "be") == "BE"

    def test_empty_means_no_preference(self):
        assert User.validated_voice_variety("nl", "") is None

    def test_a_variety_with_no_voice_is_refused(self):
        # BE is a real variety of French with real feeds behind it -- and no
        # voice. Storing it would show the learner an accent they never hear.
        try:
            User.validated_voice_variety("fr", "BE")
            assert False, "French has no Belgian voice"
        except ValueError:
            pass


class VoiceVarietyPreferenceTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.user = UserRule().user
        self.dutch = LanguageRule().nl

    def test_no_preference_is_the_default(self):
        assert UserLanguage.voice_variety_for(self.user, self.dutch) is None

    def test_a_saved_preference_comes_back(self):
        user_language = UserLanguage.find_or_create(db_session, self.user, self.dutch)
        user_language.voice_variety = "BE"
        db_session.commit()

        assert UserLanguage.voice_variety_for(self.user, self.dutch) == "BE"

    def test_the_voice_does_not_follow_the_feed(self):
        # Two settings, two questions. A learner who picked Belgian sources has
        # not thereby asked to be read to in Flemish.
        user_language = UserLanguage.find_or_create(db_session, self.user, self.dutch)
        user_language.variety = "BE"
        db_session.commit()

        assert UserLanguage.voice_variety_for(self.user, self.dutch) is None


class AudioLessonCacheKeyTest(ModelTestMixIn):
    """
    audio_lesson_meaning rows are shared across ALL users. Without the variety in
    the key, whoever generated a lesson first decides which accent every later
    learner hears.
    """

    def setUp(self):
        super().setUp()
        self.meaning = MeaningRule().meaning
        self.english = LanguageRule().en

    def _lesson(self, variety=None):
        lesson = AudioLessonMeaning(
            meaning=self.meaning,
            script="Teacher: hello",
            difficulty_level="B1",
            teacher_language=self.english,
            variety=variety,
        )
        db_session.add(lesson)
        db_session.commit()
        return lesson

    def test_a_flemish_learner_does_not_get_the_dutch_recording(self):
        self._lesson(variety=None)

        assert AudioLessonMeaning.find(
            meaning=self.meaning, teacher_language=self.english, variety="BE"
        ) is None

    def test_a_learner_with_no_preference_does_not_get_the_flemish_one(self):
        self._lesson(variety="BE")

        assert AudioLessonMeaning.find(
            meaning=self.meaning, teacher_language=self.english
        ) is None

    def test_each_variety_finds_its_own(self):
        without = self._lesson(variety=None)
        flemish = self._lesson(variety="BE")

        assert AudioLessonMeaning.find(
            meaning=self.meaning, teacher_language=self.english
        ).id == without.id
        assert AudioLessonMeaning.find(
            meaning=self.meaning, teacher_language=self.english, variety="BE"
        ).id == flemish.id
