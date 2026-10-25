import re

import sqlalchemy
from sqlalchemy.orm.exc import NoResultFound
import zeeguu.core

from zeeguu.core.model.db import db
from zeeguu.core.model.race_safe import find_or_create


class DomainName(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "domain_name"

    id = db.Column(db.Integer, primary_key=True)
    domain_name = db.Column(db.String(255), unique=True)

    def __init__(self, url):
        self.domain_name = self.extract_domain_name(url)

    def extract_domain_name(self, url):
        protocol_re = "(.*://)?"
        domain_re = "([^/?]*)"

        domain = re.findall(protocol_re + domain_re, url)[0]
        return domain[0] + domain[1]

    @classmethod
    def get_domain(self, url):
        protocol_re = "(.*://)?"
        domain_re = "([^/?]*)"
        path_re = "(.*)"

        domain = re.findall(protocol_re + domain_re, url)[0]
        return domain[0] + domain[1]

    @classmethod
    def for_url_string(cls, url_string):
        only_domain_str = DomainName.get_domain(url_string)
        try:
            return cls.query.filter(cls.domain_name == only_domain_str).one()
        except sqlalchemy.orm.exc.NoResultFound:
            # print "tried, but didn't find " + domain_url
            return cls(only_domain_str)

    @classmethod
    def find(cls, domain_url):
        return cls.query.filter(DomainName.domain_name == domain_url).one()

    @classmethod
    def find_or_create(cls, session, url: str):
        _domain = cls.get_domain(url)
        # Concurrent requests for the first url of a new domain can race here;
        # the unique domain_name lets one insert through and
        # race_safe.find_or_create recovers the other. Commits a row it
        # creates, as callers expect.
        return find_or_create(
            session,
            cls,
            {"domain_name": _domain},
            lambda: cls(_domain),
            commit=True,
        )
