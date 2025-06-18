from unittest import TestCase

import zeeguu.core
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model.domain_name import DomainName
from zeeguu.core.model.url import Url
from zeeguu.core.model.url_keyword import UrlKeyword
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from .mocking_the_web import (
    URL_SPIEGEL_NANCY,
    URL_ONION_US_MILITARY,
    URL_FAZ_LEIGHTATHLETIK,
)


db_session = zeeguu.core.model.db.session


class UrlKeywordsTest(ModelTestMixIn, TestCase):
    def test_url_keywords_from_url_1(self):
        domain = DomainName.get_domain(URL_SPIEGEL_NANCY)
        url = Url.find_or_create(db_session, URL_SPIEGEL_NANCY, domain)
        spiegel_keywords = UrlKeyword.get_url_keywords_from_url(url)
        assert "politik" == spiegel_keywords[0] and "ausland" == spiegel_keywords[1]

    def test_url_keywords_from_url_2(self):
        domain = DomainName.get_domain(URL_ONION_US_MILITARY)
        url = Url.find_or_create(db_session, URL_ONION_US_MILITARY, domain)
        onion_keywords = UrlKeyword.get_url_keywords_from_url(url)
        assert len(onion_keywords) == 0

    def test_url_keywords_from_url_3(self):
        domain = DomainName.get_domain(URL_FAZ_LEIGHTATHLETIK)
        url = Url.find_or_create(db_session, URL_FAZ_LEIGHTATHLETIK, domain)
        faz_keywords = UrlKeyword.get_url_keywords_from_url(url)
        print(faz_keywords)
        assert (
            "aktuell" == faz_keywords[0]
            and "sport" == faz_keywords[1]
            and "fussball em" == faz_keywords[2]
        )
