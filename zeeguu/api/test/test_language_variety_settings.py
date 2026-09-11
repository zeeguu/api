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


def stored_user(app, email):
    with app.app_context():
        user = User.find(email)
        return dict(
            learned_language=user.learned_language.code,
            varieties={
                each.language.code: each.feed_variety
                for each in UserLanguage.query.filter_by(user=user)
            },
        )


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
        assert save_settings(lc, learned_language="nl", feed_variety="BE").status_code == 200
        assert user_details(lc)["nl_feed_variety"] == "BE"

    def test_no_variety_is_the_default_and_stays_null(self, app, client):
        lc = logged_in(app, client, "novariety@zeeguu.test")
        assert save_settings(lc, learned_language="nl").status_code == 200
        assert user_details(lc)["nl_feed_variety"] is None

    def test_an_empty_variety_clears_a_preference(self, app, client):
        # "No preference" has to be reachable again, or a learner who picks one
        # by accident can never get back to the full feed.
        lc = logged_in(app, client, "clearing@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")
        assert save_settings(lc, learned_language="nl", feed_variety="").status_code == 200
        assert user_details(lc)["nl_feed_variety"] is None

    def test_omitting_the_variety_leaves_an_existing_one_alone(self, app, client):
        # Every client that saves settings today sends no variety at all; none of
        # them should silently wipe one.
        lc = logged_in(app, client, "untouched@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")
        assert save_settings(lc, learned_language="nl", cefr_level="3").status_code == 200
        assert user_details(lc)["nl_feed_variety"] == "BE"

    def test_a_variety_the_language_does_not_have_is_refused(self, app, client):
        lc = logged_in(app, client, "wrongvariety@zeeguu.test")
        response = save_settings(lc, learned_language="nl", feed_variety="MX")
        assert response.status_code == 400

    def test_a_refused_variety_changes_nothing_at_all(self, app, client):
        # The rejection has to reach the database as nothing, not as "the language
        # switched but the variety did not". UserLanguage.find_or_create commits,
        # so validating after it would put the switch beyond the caller's rollback
        # -- and only for a language the user has no row for yet, which is exactly
        # when someone picks a variety.
        lc = logged_in(app, client, "nopartial@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")
        before = stored_user(app, "nopartial@zeeguu.test")

        response = save_settings(lc, learned_language="pt", feed_variety="MX")

        assert response.status_code == 400
        assert stored_user(app, "nopartial@zeeguu.test") == before


class TestVarietyWithoutALanguageChange:
    """
    A client that changed only the variety sends only the variety.
    """

    def test_a_lone_variety_is_saved_for_the_learned_language(self, app, client):
        lc = logged_in(app, client, "lone@zeeguu.test")
        save_settings(lc, learned_language="nl")

        assert save_settings(lc, feed_variety="BE").status_code == 200
        assert user_details(lc)["nl_feed_variety"] == "BE"

    def test_a_lone_variety_can_clear_the_preference(self, app, client):
        lc = logged_in(app, client, "loneclear@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")

        assert save_settings(lc, feed_variety="").status_code == 200
        assert user_details(lc)["nl_feed_variety"] is None

    def test_a_lone_variety_of_another_language_is_refused(self, app, client):
        lc = logged_in(app, client, "lonewrong@zeeguu.test")
        save_settings(lc, learned_language="nl")

        assert save_settings(lc, feed_variety="BR").status_code == 400
        assert user_details(lc)["nl_feed_variety"] is None

    def test_saving_something_else_leaves_the_variety_alone(self, app, client):
        lc = logged_in(app, client, "othersave@zeeguu.test")
        save_settings(lc, learned_language="nl", feed_variety="BE")

        assert save_settings(lc, name="Renamed").status_code == 200
        assert user_details(lc)["nl_feed_variety"] == "BE"

    def test_the_catalogue_is_served_to_the_client(self, app, client):
        # Empty here because the test database has no tagged feeds: what is
        # offered comes from the feeds, not from the fixed list. The list itself
        # is covered in test_language_varieties.
        varieties = json.loads(client.get("/system_languages").data)["varieties"]
        assert isinstance(varieties, dict)
        assert "es" not in varieties

    def test_belgium_is_saved_under_whichever_language_asked_for_it(self, app, client):
        # The same country code belongs to two languages, and each learner's row
        # has to carry it under their own -- a Flemish reader and a Walloon one
        # both store "BE" and must not be told they mean the same thing.
        lc = logged_in(app, client, "bilingual@zeeguu.test")

        save_settings(lc, learned_language="nl", feed_variety="BE")
        save_settings(lc, learned_language="fr", feed_variety="BE")

        details = user_details(lc)
        assert details["nl_feed_variety"] == "BE"
        assert details["fr_feed_variety"] == "BE"
