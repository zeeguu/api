# import warnings
# warnings.filterwarnings("ignore", category=DeprecationWarning)

from faker import Faker

from unittest import TestCase

from zeeguu.core.test.conftest import get_shared_app, get_mock, cleanup_tables
from zeeguu.core.test.fixtures import add_context_types, add_source_types


class ModelTestMixIn(TestCase):
    def setUp(self):
        self.faker = Faker()
        add_context_types()
        add_source_types()

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
