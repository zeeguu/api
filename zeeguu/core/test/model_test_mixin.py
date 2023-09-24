# import warnings
# warnings.filterwarnings("ignore", category=DeprecationWarning)

import requests_mock

from faker import Faker

from unittest import TestCase

from zeeguu.api.app import create_app
from zeeguu.core.test.mocking_the_web import mock_requests_get


class ModelTestMixIn(TestCase):
    def setUp(self):
        self.faker = Faker()

    def tearDown(self):
        super(ModelTestMixIn, self).tearDown()
        self.faker = None

        # sometimes the tearDown freezes on drop_all
        # and it seems that it's because there's still
        # a session open somewhere. Better call first:
        from zeeguu.core.model import db

        db.session.close()

        db.drop_all()

    def run(self, result=None):
        # For the unit tests we use several HTML documents
        # that are stored locally so we don't have to download
        # them for every test
        # To do this we mock requests.get
        self.app = create_app(testing=True)

        with requests_mock.Mocker() as m:
            mock_requests_get(m)
            with self.app.app_context():
                super(ModelTestMixIn, self).run(result)
