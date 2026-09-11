from unittest import TestCase

from zeeguu.core.language.varieties import (
    catalogue,
    has_varieties,
    is_supported,
    variety_name,
    varieties_for,
)
from zeeguu.core.model.user import User


class LanguageVarietiesTest(TestCase):
    """
    The catalogue and the validation that guards it. Neither touches the
    database: a variety is not a row in `language`, and deliberately so.
    """

    def test_only_languages_that_divide_by_country_are_offered(self):
        assert varieties_for("nl") == ("NL", "BE")
        assert varieties_for("fr") == ("FR", "BE")
        assert varieties_for("pt") == ("PT", "BR")
        # Spanish splits Spain against a macro-region, which no country code can
        # express; the rest have no national split worth the setting.
        assert varieties_for("es") == ()
        assert not has_varieties("da")

    def test_a_variety_has_a_name_a_person_can_read(self):
        assert variety_name("nl", "BE") == "Belgian Dutch"
        assert variety_name("pt", "PT") == "European Portuguese"

    def test_a_variety_with_no_adjective_is_named_the_long_way(self):
        # These names end up in LLM prompts, where "France French" is a puzzle.
        assert variety_name("fr", "FR") == "French from France"
        assert variety_name("nl", "NL") == "Dutch from the Netherlands"

    def test_an_unknown_variety_falls_back_to_the_language_name(self):
        assert variety_name("nl", "ZZ") == "Dutch"

    def test_catalogue_carries_every_variety_with_its_name(self):
        assert catalogue()["nl"] == [
            dict(country="NL", name="Dutch from the Netherlands"),
            dict(country="BE", name="Belgian Dutch"),
        ]

    def test_is_supported_rejects_a_country_of_another_language(self):
        assert is_supported("nl", "BE")
        assert not is_supported("pt", "BE")

    def test_belgium_belongs_to_both_its_languages(self):
        # The country is bilingual; a learner of either can want its half.
        assert is_supported("nl", "BE")
        assert is_supported("fr", "BE")
        assert variety_name("nl", "BE") == "Belgian Dutch"
        assert variety_name("fr", "BE") == "Belgian French"


class ValidatedVarietyTest(TestCase):
    def test_a_variety_is_stored_uppercased(self):
        assert User.validated_variety("nl", "be") == "BE"

    def test_empty_means_no_preference_rather_than_a_rejected_save(self):
        assert User.validated_variety("nl", "") is None
        assert User.validated_variety("nl", "   ") is None

    def test_a_variety_the_language_does_not_have_is_refused(self):
        # Storing it would leave the settings screen showing a preference that
        # nothing downstream honours.
        for unsupported in ["MX", "FR", "ZZ"]:
            try:
                User.validated_variety("nl", unsupported)
                assert False, f"{unsupported} should not be a variety of Dutch"
            except ValueError:
                pass

    def test_a_language_with_no_varieties_accepts_none_of_them(self):
        try:
            User.validated_variety("da", "DK")
            assert False, "Danish has no varieties"
        except ValueError:
            pass
