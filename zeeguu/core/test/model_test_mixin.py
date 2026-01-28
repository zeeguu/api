# import warnings
# warnings.filterwarnings("ignore", category=DeprecationWarning)

from faker import Faker

from unittest import TestCase

from zeeguu.core.test.conftest import get_shared_app, get_mock, cleanup_tables, init_fixtures_once


class ModelTestMixIn(TestCase):
    def setUp(self):
        self.faker = Faker()
        init_fixtures_once()

    def tearDown(self):
        super(ModelTestMixIn, self).tearDown()
        self.faker = None

        from zeeguu.core.model.db import db

        db.session.close()
        cleanup_tables()

    def run(self, result=None):
        self.app = get_shared_app()
        get_mock()

        with self.app.app_context():
            super(ModelTestMixIn, self).run(result)
