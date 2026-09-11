import json

from zeeguu.api.test.fixtures import client, LoggedInClient
from zeeguu.core.model import Language, User

TEST_PASS = "test"


def logged_in(app, client, email):
    # set_learned_language looks the language up strictly, and the test database
    # starts with only the languages other fixtures happened to create.
    with app.app_context():
        Language.find_or_create("nl")
    return LoggedInClient(client, email=email, password=TEST_PASS)


def save_settings(lc, **data):
    return lc.response_from_post("/user_settings", data=data)


def user_details(lc):
    return lc.get("/get_user_details")


class TestLanguageVarietyRoundTrip:
    """
    A variety only exists to be honoured downstream -- by the feed, the voice,
    the translator. That starts with it surviving a save and coming back out.
    """

    def test_a_variety_saved_comes_back_under_its_language(self, app, client):
        lc = logged_in(app, client, "flemish@zeeguu.test")
        assert save_settings(lc, learned_language="nl", variety="BE").status_code == 200
        assert user_details(lc)["nl_variety"] == "BE"

    def test_no_variety_is_the_default_and_stays_null(self, app, client):
        lc = logged_in(app, client, "novariety@zeeguu.test")
        assert save_settings(lc, learned_language="nl").status_code == 200
        assert user_details(lc)["nl_variety"] is None

    def test_an_empty_variety_clears_a_preference(self, app, client):
        # "No preference" has to be reachable again, or a learner who picks one
        # by accident can never get back to the full feed.
        lc = logged_in(app, client, "clearing@zeeguu.test")
        save_settings(lc, learned_language="nl", variety="BE")
        assert save_settings(lc, learned_language="nl", variety="").status_code == 200
        assert user_details(lc)["nl_variety"] is None

    def test_omitting_the_variety_leaves_an_existing_one_alone(self, app, client):
        # Every client that saves settings today sends no variety at all; none of
        # them should silently wipe one.
        lc = logged_in(app, client, "untouched@zeeguu.test")
        save_settings(lc, learned_language="nl", variety="BE")
        assert save_settings(lc, learned_language="nl", cefr_level="3").status_code == 200
        assert user_details(lc)["nl_variety"] == "BE"

    def test_a_variety_the_language_does_not_have_is_refused(self, app, client):
        lc = logged_in(app, client, "wrongvariety@zeeguu.test")
        response = save_settings(lc, learned_language="nl", variety="MX")
        assert response.status_code == 400

    def test_the_catalogue_is_served_to_the_client(self, app, client):
        varieties = json.loads(client.get("/system_languages").data)["varieties"]
        assert [each["country"] for each in varieties["nl"]] == ["NL", "BE"]
        assert "es" not in varieties
