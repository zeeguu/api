from threading import Thread
from unittest import TestCase
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.url_rule import UrlRule
import zeeguu.core.model
from zeeguu.core.model import Url, DomainName

db_session = zeeguu.core.model.db.session


class UrlTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.url_rule = UrlRule()

    def test_domain_plus_path_must_be_unique(self):

        _url = self.url_rule.url.as_string()
        _title = self.url_rule.url.title
        _domain = DomainName.get_domain(_url)

        with self.assertRaises(Exception) as context:
            domain = DomainName.find(_domain)
            url = Url(_url, _title, domain)
            db_session.add(url)
            db_session.commit()

        self.assertTrue("Duplicate entry" or "IntegrityError" in str(context.exception))

    def test_find_or_create_works(self):

        _url = self.url_rule.url.as_string()
        _title = self.url_rule.url.title

        url = Url.find_or_create(db_session, _url, _title)

        self.assertEqual(url.title, _title)

    def test_try_to_get_race_condition(self):

        _url = self.url_rule.url.as_string()
        _title = self.url_rule.url.title

        def threaded_create_url():
            url = Url.find_or_create(db_session, _url, _title)

        threads = []

        for i in range(0):  # multithreaded connections freeze on mysqldb.
            # so this is here to be tested manually and killed for now...
            t = Thread(target=threaded_create_url, args=())
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        url = Url.find_or_create(db_session, _url, _title)
        self.assertEqual(url.title, _title)
