from json import loads

import pytest
import requests_mock

import zeeguu
from zeeguu.api.app import create_app
from zeeguu.core.test.mocking_the_web import mock_requests_get
from zeeguu.core.test.mocking_the_web import URL_SPIEGEL_VENEZUELA
from zeeguu.core.model.db import db

db_session = db.session


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture
def test_app(app):
    yield app


@pytest.fixture
def logged_in_client(app, _mock_web):
    with app.test_client() as client:
        logged_in_client = LoggedInClient(client)
        yield logged_in_client


@pytest.fixture
def logged_in_teacher(app, _mock_web):
    with app.test_client() as client:
        logged_in_client = LoggedInTeacher(client)
        yield logged_in_client


class LoggedInClient:
    def __init__(self, client):
        self.client = client

        # Creating a user and returning also the session
        test_user_data = dict(password="test", username="test", learned_language="de")
        self.email = "i@mir.lu"
        response = self.client.post(f"/add_user/{self.email}", data=test_user_data)
        assert response.status_code == 200

        self.session = response.data.decode("utf-8")
        print(">>>>>>>>> <<<<<<")
        print(response.data)
        print(self.session)

    def append_session(self, url):
        if "?" in url:
            return url + "&session=" + self.session
        return url + "?session=" + self.session

    def get(self, endpoint):
        url = self.append_session(endpoint)
        result = self.client.get(url).data
        try:
            return loads(result)
        except:
            return result

    """
    This is a bit strange: the return type is data in case of 200
    and a response otherwise; so one can never test the status
    code for a successful response
    """

    def response_from_post(self, endpoint, data=dict()):

        response = self.client.post(self.append_session(endpoint), data=data)
        return response

    def post(self, endpoint, data=dict(), json=None):
        if json is not None:
            response = self.client.post(self.append_session(endpoint), json=json)
        else:
            response = self.client.post(self.append_session(endpoint), data=data)
        try:
            return loads(response.data)
        except Exception as e:
            print("Failed json parsing: ", e)
            return response.data


class LoggedInTeacher(LoggedInClient):

    def __init__(self, client):
        super().__init__(client)
        self._upgrade_to_teacher()

    def _upgrade_to_teacher(self):
        from zeeguu.core.model import User, Teacher

        from zeeguu.core.model.db import db

        u = User.find(self.email)
        db_session.add(Teacher(u))
        db_session.commit()


def create_and_get_article(client):

    return client.post("/find_or_create_article", data=dict(url=URL_SPIEGEL_VENEZUELA))


def add_one_bookmark(logged_in_client):
    from zeeguu.core.model.context_identifier import ContextIdentifier
    from zeeguu.core.model.context_type import ContextType

    article = create_and_get_article(logged_in_client)
    context_i = ContextIdentifier(ContextType.ARTICLE_TITLE, None, article["id"])
    bookmark = logged_in_client.post(
        "/contribute_translation/de/en",
        json={
            "word": "hinter",
            "translation": "behind",
            "context": "stellt sich hinter Präsident",
            "url": URL_SPIEGEL_VENEZUELA,
            "source_id": article["source_id"],
            "context_identifier": context_i.as_dictionary(),
        },
    )
    bookmark_id = bookmark["bookmark_id"]

    return bookmark_id


def add_context_types():
    from zeeguu.core.model.context_type import ContextType

    for type in ContextType.ALL_TYPES:
        ContextType.find_or_create(db_session, type, commit=False)
    db_session.commit()


def add_source_types():
    from zeeguu.core.model.source_type import SourceType

    for type in SourceType.ALL_TYPES:
        SourceType.find_or_create(db_session, type, commit=False)
    db_session.commit()
