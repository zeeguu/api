from zeeguu.api.test.fixtures import client, LoggedInClient
from zeeguu.core.model import Language, User, UserLanguage

TEST_PASS = "test"


def logged_in(app, client, email, username, learned_language="de"):
    # set_learned_language looks the language up strictly, and the test database
    # starts with only the languages other fixtures happened to create.
    with app.app_context():
        Language.find_or_create("de")
        Language.find_or_create("pt")
    return LoggedInClient(
        client,
        email=email,
        password=TEST_PASS,
        username=username,
        learned_language=learned_language,
    )


def stored_user(app, email):
    """
    Everything /user_settings can write, as the database has it. A save that the
    endpoint refused has to leave all of this exactly as it found it.
    """
    with app.app_context():
        user = User.find(email)
        return dict(
            name=user.name,
            username=user.username,
            email=user.email,
            native_language=user.native_language.code,
            learned_language=user.learned_language.code,
            languages={
                each.language.code: (each.reading_news, each.doing_exercises, each.cefr_level)
                for each in UserLanguage.query.filter_by(user=user)
            },
        )


def save_settings(lc, **data):
    return lc.response_from_post("/user_settings", data=data)


class TestARefusedSaveChangesNothing:
    """
    /user_settings answers 400 for a request it will not honour, and the client
    reads that as "nothing was written". Saving the learned language goes through
    UserLanguage.find_or_create, which commits, so a check that runs after it
    would make that answer a lie -- and only for a language the user has no row
    for yet, which is exactly when someone switches language.
    """

    def test_an_email_someone_else_holds_leaves_the_language_alone(self, app, client):
        logged_in(app, client, "holder@zeeguu.test", "holder")
        lc = logged_in(app, client, "switcher@zeeguu.test", "switcher")
        save_settings(lc, learned_language="de")
        before = stored_user(app, "switcher@zeeguu.test")

        response = save_settings(
            lc, learned_language="pt", email="holder@zeeguu.test"
        )

        assert response.status_code == 400
        assert stored_user(app, "switcher@zeeguu.test") == before

    def test_an_email_someone_else_holds_leaves_the_name_alone(self, app, client):
        # The name is assigned before the language is saved, so the commit inside
        # find_or_create would carry it along with everything else.
        logged_in(app, client, "nameholder@zeeguu.test", "nameholder")
        lc = logged_in(app, client, "renamer@zeeguu.test", "renamer")
        before = stored_user(app, "renamer@zeeguu.test")

        response = save_settings(
            lc,
            name="Should Not Stick",
            learned_language="pt",
            email="nameholder@zeeguu.test",
        )

        assert response.status_code == 400
        assert stored_user(app, "renamer@zeeguu.test") == before

    def test_a_username_someone_else_holds_changes_nothing(self, app, client):
        logged_in(app, client, "namesake@zeeguu.test", "namesake")
        # Signup generates the username rather than taking the submitted one, so
        # the name to collide with has to come back out of the database.
        taken_username = stored_user(app, "namesake@zeeguu.test")["username"]
        lc = logged_in(app, client, "copycat@zeeguu.test", "copycat")
        before = stored_user(app, "copycat@zeeguu.test")

        response = save_settings(lc, learned_language="pt", username=taken_username)

        assert response.status_code == 400
        assert stored_user(app, "copycat@zeeguu.test") == before


class TestALanguageCodeNobodyKnows:
    """
    Language.find raises sqlalchemy's NoResultFound, which is neither ValueError
    nor IntegrityError, so a typo in a language code used to escape the endpoint
    as a 500 -- a server error for a malformed request.
    """

    def test_an_unknown_learned_language_is_refused_with_a_400(self, app, client):
        lc = logged_in(app, client, "typo@zeeguu.test", "typo")

        assert save_settings(lc, learned_language="xx").status_code == 400

    def test_an_unknown_native_language_is_refused_with_a_400(self, app, client):
        lc = logged_in(app, client, "typonative@zeeguu.test", "typonative")

        assert save_settings(lc, native_language="xx").status_code == 400

    def test_an_unknown_language_changes_nothing(self, app, client):
        lc = logged_in(app, client, "typonothing@zeeguu.test", "typonothing")
        before = stored_user(app, "typonothing@zeeguu.test")

        response = save_settings(lc, name="Should Not Stick", learned_language="xx")

        assert response.status_code == 400
        assert stored_user(app, "typonothing@zeeguu.test") == before


class TestTheRefusalDoesNotBreakTheNextSave:

    def test_a_good_save_still_goes_through_after_a_refused_one(self, app, client):
        logged_in(app, client, "blocker@zeeguu.test", "blocker")
        lc = logged_in(app, client, "recovering@zeeguu.test", "recovering")

        assert save_settings(lc, email="blocker@zeeguu.test").status_code == 400
        assert save_settings(lc, learned_language="pt").status_code == 200
        assert stored_user(app, "recovering@zeeguu.test")["learned_language"] == "pt"
