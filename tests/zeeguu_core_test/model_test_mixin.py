# import warnings
# warnings.filterwarnings("ignore", category=DeprecationWarning)

import requests_mock
import zeeguu_core.model

from faker import Faker

from unittest import TestCase

from zeeguu_core_test.test_data.mocking_the_web import mock_requests_get


class ModelTestMixIn(TestCase):
    db = zeeguu_core.db

    def setUp(self):
        self.faker = Faker()
        self.db.create_all()

    def tearDown(self):
        super(ModelTestMixIn, self).tearDown()
        self.faker = None

        # sometimes the tearDown freezes on drop_all
        # and it seems that it's because there's still
        # a session open somewhere. Better call first:
        self.db.session.close()

        self.db.drop_all()

    def run(self, result=None):

        # For the unit tests we use several HTML documents
        # that are stored locally so we don't have to download
        # them for every test
        # To do this we mock requests.get
        with requests_mock.Mocker() as m:
            mock_requests_get(m)
            super(ModelTestMixIn, self).run(result)
