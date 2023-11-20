import json

import pytest
import requests_mock

from zeeguu.api.app import create_app
import zeeguu
from zeeguu.core.test.mocking_the_web import mock_requests_get


@pytest.fixture
def client():
    app = create_app(testing=True)

    with app.test_client() as client:
        with app.app_context():
            zeeguu.core.model.db.create_all()

            yield client

    with app.app_context():
        zeeguu.core.model.db.session.remove()
        zeeguu.core.model.db.drop_all()


@pytest.fixture
def test_app():
    app = create_app(testing=True)

    with app.app_context():
        zeeguu.core.model.db.create_all()

        yield app

    with app.app_context():
        zeeguu.core.model.db.session.remove()
        zeeguu.core.model.db.drop_all()


@pytest.fixture
def logged_in_client():
    app = create_app(testing=True)

    with requests_mock.Mocker() as m:
        mock_requests_get(m)

        with app.test_client() as client:
            with app.app_context():
                zeeguu.core.model.db.create_all()

                logged_in_client = LoggedInClient(client)

                yield logged_in_client

    with app.app_context():
        zeeguu.core.model.db.session.remove()
        zeeguu.core.model.db.drop_all()


@pytest.fixture
def logged_in_teacher():
    app = create_app(testing=True)

    with requests_mock.Mocker() as m:
        mock_requests_get(m)

        with app.test_client() as client:
            with app.app_context():
                zeeguu.core.model.db.create_all()

                logged_in_client = LoggedInTeacher(client)

                yield logged_in_client

    with app.app_context():
        zeeguu.core.model.db.session.remove()
        zeeguu.core.model.db.drop_all()


class LoggedInClient():
    def __init__(self, client):
        self.client = client

        # Creating a user and returning also the session
        test_user_data = dict(
            password="test", username="test", learned_language="de"
        )
        self.email = "i@mir.lu"
        response = self.client.post(f"/add_user/{self.email}", data=test_user_data)
        assert response.status_code == 200

        self.session = int(response.data)

    def append_session(self, url):
        if "?" in url:
            return url + "&session=" + str(self.session)
        return url + "?session=" + str(self.session)

    def get(self, endpoint):
        url = self.append_session(endpoint)
        result = self.client.get(url).data
        try:
            return json.loads(result)
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

    def post(self, endpoint, data=dict()):
        response = self.client.post(self.append_session(endpoint), data=data)
        try:
            return json.loads(response.data)
        except:
            return response.data


class LoggedInTeacher(LoggedInClient):

    def __init__(self, client):
        super().__init__(client)
        self._upgrade_to_teacher()

    def _upgrade_to_teacher(self):
        from zeeguu.core.model import User, Teacher

        from zeeguu.core.model import db

        u = User.find(self.email)
        db.session.add(Teacher(u))
        db.session.commit()


def add_one_bookmark(logged_in_client):
    # Create one bookmark too
    bookmark = logged_in_client.post("/contribute_translation/de/en", data=dict(
        word="Freund",
        translation="friend",
        context="Mein Freund lächelte",
        url="http://www.derkleineprinz-online.de/text/2-kapitel/",
    ))

    bookmark_id = bookmark["bookmark_id"]

    return bookmark_id
