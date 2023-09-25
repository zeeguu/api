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


class LoggedInClient():
    def __init__(self, client):
        self.client = client

        # Creating a user and returning also the session
        test_user_data = dict(
            password="test", username="test", learned_language="de"
        )
        response = self.client.post(f"/add_user/i@mir.lu", data=test_user_data)
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

    def post(self, endpoint, data=dict()):

        result = self.client.post(self.append_session(endpoint), data=data).data
        try:
            return json.loads(result)
        except:
            return result


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
