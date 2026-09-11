import json

from zeeguu.api.test.fixtures import client, LoggedInClient
from zeeguu.core.model import Language, User, UserLanguage

TEST_PASS = "test"


def logged_in(app, client, email):
    # set_learned_language looks the language up strictly, and the test database
    # starts with only the languages other fixtures happened to create.
    with app.app_context():
        Language.find_or_create("nl")
        Language.find_or_create("fr")
        Language.find_or_create("pt")
    return LoggedInClient(client, email=email, password=TEST_PASS)


def save_settings(lc, **data):
    return lc.response_from_post("/user_settings", data=data)


def user_details(lc):
    return lc.get("/get_user_details")


class TestDialectRoundTrip:
    """
    Which variety of the language the learner is studying. A separate setting
    from the feed's, because "Everywhere" is a coherent answer to which country's
    news to read and an incoherent one to which dialect you are learning.
    """

    def test_a_dialect_saved_comes_back_under_its_language(self, app, client):
        lc = logged_in(app, client, "flemishvoice@zeeguu.test")
        assert save_settings(lc, learned_language="nl", dialect="BE").status_code == 200
        assert user_details(lc)["nl_dialect"] == "BE"

    def test_no_dialect_is_the_default_and_stays_null(self, app, client):
        lc = logged_in(app, client, "novoice@zeeguu.test")
        assert save_settings(lc, learned_language="nl").status_code == 200
        assert user_details(lc)["nl_dialect"] is None

    def test_an_empty_dialect_clears_a_preference(self, app, client):
        lc = logged_in(app, client, "clearvoice@zeeguu.test")
        save_settings(lc, learned_language="nl", dialect="BE")
        assert save_settings(lc, dialect="").status_code == 200
        assert user_details(lc)["nl_dialect"] is None

    def test_the_two_settings_do_not_touch_each_other(self, app, client):
        # Picking a Brazilian voice must not narrow the feed to Brazilian sources,
        # and picking Belgian sources must not change the accent.
        lc = logged_in(app, client, "twosettings@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")

        assert save_settings(lc, dialect="NL").status_code == 200

        details = user_details(lc)
        assert details["nl_feed_variety"] == "BE"
        assert details["nl_dialect"] == "NL"

    def test_a_variety_with_no_voice_is_refused(self, app, client):
        # Belgian French has feeds and no Google voice. Accepting it would leave
        # the settings screen showing an accent the learner never hears.
        lc = logged_in(app, client, "walloon@zeeguu.test")
        save_settings(lc, learned_language="fr")

        assert save_settings(lc, dialect="BE").status_code == 400
        assert user_details(lc)["fr_dialect"] is None

    def test_a_refused_dialect_changes_nothing_else(self, app, client):
        lc = logged_in(app, client, "voicenopartial@zeeguu.test")
        save_settings(lc, learned_language="nl", dialect="BE")

        assert save_settings(lc, learned_language="fr", dialect="BE").status_code == 400
        assert user_details(lc)["learned_language"] == "nl"

    def test_a_language_switch_and_a_voice_land_on_the_new_language(self, app, client):
        lc = logged_in(app, client, "switchvoice@zeeguu.test")
        save_settings(lc, learned_language="nl", dialect="BE")

        assert save_settings(lc, learned_language="pt", dialect="BR").status_code == 200

        details = user_details(lc)
        assert details["pt_dialect"] == "BR"
        assert details["nl_dialect"] == "BE"

    def test_the_dialect_catalogue_is_served_to_the_client(self, app, client):
        catalogue = json.loads(client.get("/system_languages").data)["dialects"]

        assert [each["country"] for each in catalogue["nl"]] == ["NL", "BE"]
        assert [each["country"] for each in catalogue["pt"]] == ["PT", "BR"]
        # French has two varieties in the feed catalogue and one voice, so it
        # offers no voice control at all.
        assert "fr" not in catalogue


class TestTheOldVarietyWireName:
    """
    The native apps ship a frozen copy of the web bundle, so they cannot be
    updated in step with the API. App 1.3.3 -- in App Store review when
    feed_variety was deployed -- still speaks the old name in both directions.
    These tests are what makes dropping the compatibility a decision rather than
    an accident.
    """

    def test_the_old_name_still_saves(self, app, client):
        lc = logged_in(app, client, "oldclient@zeeguu.test")

        assert save_settings(lc, learned_language="nl", variety="BE").status_code == 200
        assert user_details(lc)["nl_feed_variety"] == "BE"

    def test_the_old_name_still_comes_back(self, app, client):
        # A 1.3.3 settings screen reads this key; without it the selector shows
        # "Everywhere" whatever is stored, and the empty-feed explanation -- which
        # gates on the same read -- disappears too.
        lc = logged_in(app, client, "oldread@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")

        assert user_details(lc)["nl_variety"] == "BE"

    def test_the_old_name_can_still_clear_a_preference(self, app, client):
        lc = logged_in(app, client, "oldclear@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")

        assert save_settings(lc, variety="").status_code == 200
        assert user_details(lc)["nl_feed_variety"] is None

    def test_the_new_name_wins_when_a_client_sends_both(self, app, client):
        lc = logged_in(app, client, "bothnames@zeeguu.test")

        save_settings(lc, learned_language="nl", feed_variety="BE", variety="NL")

        assert user_details(lc)["nl_feed_variety"] == "BE"

    def test_sending_neither_still_leaves_the_preference_alone(self, app, client):
        # The reason the fallback checks for the key rather than for a value:
        # every client that saves settings without touching the variety must not
        # wipe one.
        lc = logged_in(app, client, "neithername@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")

        assert save_settings(lc, name="Renamed").status_code == 200
        assert user_details(lc)["nl_feed_variety"] == "BE"


class TestTheOldVarietyWireName:
    """
    The native apps ship a frozen copy of the web bundle, so they cannot be
    updated in step with the API. App 1.3.3 -- in App Store review when
    feed_variety was deployed -- speaks the old name in both directions.

    These tests are also the reminder: when 1.3.3 has drained, deleting the
    fallback fails them, which is how the removal becomes a decision rather than
    an accident.
    """

    def test_the_old_name_still_saves(self, app, client):
        lc = logged_in(app, client, "oldclient@zeeguu.test")

        assert save_settings(lc, learned_language="nl", variety="BE").status_code == 200
        assert user_details(lc)["nl_feed_variety"] == "BE"

    def test_the_old_name_still_comes_back(self, app, client):
        # A 1.3.3 settings screen reads this key. Without it the selector shows
        # "Everywhere" whatever is stored, and the explanation for a feed narrowed
        # to one country -- which gates on the same read -- disappears too.
        lc = logged_in(app, client, "oldread@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")

        assert user_details(lc)["nl_variety"] == "BE"

    def test_the_old_name_can_still_clear_a_preference(self, app, client):
        lc = logged_in(app, client, "oldclear@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")

        assert save_settings(lc, variety="").status_code == 200
        assert user_details(lc)["nl_feed_variety"] is None

    def test_the_new_name_wins_when_a_client_sends_both(self, app, client):
        lc = logged_in(app, client, "bothnames@zeeguu.test")

        save_settings(lc, learned_language="nl", feed_variety="BE", variety="NL")

        assert user_details(lc)["nl_feed_variety"] == "BE"

    def test_sending_neither_still_leaves_the_preference_alone(self, app, client):
        # Why the fallback tests for the key rather than for a value: every client
        # that saves settings without touching the variety must not wipe one.
        lc = logged_in(app, client, "neithername@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")

        assert save_settings(lc, name="Renamed").status_code == 200
        assert user_details(lc)["nl_feed_variety"] == "BE"
