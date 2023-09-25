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
def client_with_new_user_and_session():
    app = create_app(testing=True)

    with requests_mock.Mocker() as m:
        mock_requests_get(m)

        with app.test_client() as client:
            with app.app_context():
                zeeguu.core.model.db.create_all()

                # Creating a user and returning also the session
                test_user_data = dict(
                    password="test", username="test", learned_language="de"
                )
                response = client.post(f"/add_user/test@test.es", data=test_user_data)
                assert response.status_code == 200

                session = int(response.data)

                def append_session(url):
                    return url + "?session=" + str(session)

        yield client, session, append_session

    with app.app_context():
        zeeguu.core.model.db.session.remove()
        zeeguu.core.model.db.drop_all()


@pytest.fixture
def client_with_new_user_bookmark_and_session():
    app = create_app(testing=True)

    with requests_mock.Mocker() as m:
        mock_requests_get(m)

        with app.test_client() as client:
            with app.app_context():
                zeeguu.core.model.db.create_all()

                # Creating a user and returning also the session
                test_user_data = dict(
                    password="test", username="test", learned_language="de"
                )
                response = client.post(f"/add_user/test@test.es", data=test_user_data)
                assert response.status_code == 200

                session = int(response.data)

                def append_session(url):
                    return url + "?session=" + str(session)

                def client_get(endpoint):
                    return json.loads(client.get(append_session(endpoint)).data)

                def client_post(endpoint, payload=dict()):
                    result = client.post(append_session(endpoint), data=payload).data
                    try:
                        return json.loads(result)
                    except:
                        return result

                # Create one bookmark too
                bookmark = client_post("/contribute_translation/de/en", dict(
                    word="Freund",
                    translation="friend",
                    context="Mein Freund lächelte",
                    url="http://www.derkleineprinz-online.de/text/2-kapitel/",
                ))

                bookmark_id = bookmark["bookmark_id"]

        yield client_get, client_post, bookmark_id

    with app.app_context():
        zeeguu.core.model.db.session.remove()
        zeeguu.core.model.db.drop_all()
