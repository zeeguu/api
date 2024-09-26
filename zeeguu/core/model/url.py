import re
from urllib.parse import urlparse
from urllib.request import urlopen

import sqlalchemy.orm
from requests import Request
from sqlalchemy import UniqueConstraint

import zeeguu.core
import time
import random

from zeeguu.core.model import db

from zeeguu.core.model.domain_name import DomainName


class Url(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(2083))

    path = db.Column(db.String(255))

    domain_name_id = db.Column(db.Integer, db.ForeignKey(DomainName.id))
    domain = db.relationship(DomainName)

    __table_args__ = (
        UniqueConstraint(
            "path", "domain_name_id", name="_path_domain_unique_constraint"
        ),
        {"mysql_collate": "utf8_bin"},
    )

    def __init__(self, url: str, title: str = "", domain: DomainName = None):

        self.path = Url.get_path(url)
        self.title = title
        if domain:
            self.domain = domain
        else:
            self.domain = DomainName.for_url_string(url)

    def __str__(self):
        return self.as_string()

    def title_if_available(self):
        if self.title != "":
            return self.title
        return self.as_string()

    def as_string(self):
        return self.domain.domain_name + self.path

    def as_canonical_string(self):
        return self.as_string().split("articleURL=")[-1]

    def render_link(self, link_text=None):
        if not link_text:
            _title = self.title
        else:
            _title = link_text
        if self.as_string() != "":
            return '<a href="' + self.as_string() + '">' + _title + "</a>"
        else:
            return ""

    def domain_name(self):
        return self.domain.domain_name

    @classmethod
    def get_domain(cls, url):
        protocol_re = "(.*://)?"
        domain_re = "([^/?]*)"
        path_re = "(.*)"

        domain = re.findall(protocol_re + domain_re, url)[0]
        return domain[0] + domain[1]

    @classmethod
    def get_path(cls, url: str):
        protocol_re = "(.*://)?"
        domain_re = "([^/?]*)"
        path_re = "(.*)"

        domain = re.findall(protocol_re + domain_re + path_re, url)[0]
        return domain[2]

    @classmethod
    def find_or_create(cls, session: "Session", _url: str, title: str = ""):

        domain = DomainName.find_or_create(session, _url)
        path = Url.get_path(_url)

        try:
            return cls.query.filter(cls.path == path).filter(cls.domain == domain).one()
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            try:
                new = cls(_url, title, domain)
                session.add(new)
                session.commit()
                return new
            except sqlalchemy.exc.IntegrityError or sqlalchemy.exc.DatabaseError:
                for i in range(10):
                    try:
                        print("doing a rollback")
                        session.rollback()
                        domain = DomainName.find_or_create(session, _url)
                        path = Url.get_path(_url)
                        print(
                            f"after rollback trying to find again: {domain.domain_name} + {path}"
                        )
                        u = (
                            cls.query.filter(cls.path == path)
                            .filter(cls.domain == domain)
                            .first()
                        )
                        print("Found url after recovering from race")
                        return u
                    except Exception as e:
                        print("Exception of second degree in url..." + str(i) + str(e))
                        time.sleep(random.randrange(1, 10) * 0.1)
                        from sentry_sdk import capture_message

                        capture_message(
                            "Exception of second degree in url..." + str(i) + str(e)
                        )

                        continue
                    break

    @classmethod
    def find(cls, url, title=""):
        d = DomainName.find(Url.get_domain(url))
        return (
            cls.query.filter(cls.path == Url.get_path(url))
            .filter(cls.domain == d)
            .one()
        )

    # To delete... nobody seems to use this.
    # @classmethod
    # def follow_redirects_and_extract_canonical_url(cls, url: str):
    #     """
    #         does two things...
    #         follows the redirects
    #         and extracts the canonical url of the final
    #     :param url:
    #     :return:
    #     """
    #
    #     if not hasattr(cls, 'canonical_url_cache'):
    #         cls.canonical_url_cache = {}
    #
    #     cached = cls.canonical_url_cache.get(url, None)
    #     if cached:
    #         return cached
    #
    #     without_zeeguu_prefix = url.split('articleURL=')[-1]
    #
    #     req = Request(without_zeeguu_prefix, headers={'User-Agent': 'Chrome/35.0.1916.47'})
    #     res = urlopen(req)
    #     final = res.geturl()
    #
    #     o = urlparse(final)
    #
    #     canonical_url = o.scheme + "://" + o.netloc + o.path
    #
    #     cls.canonical_url_cache[url] = canonical_url
    #     return canonical_url

    @classmethod
    def extract_canonical_url(self, url: str):

        from urllib.parse import urlparse

        u = urlparse(url)

        return f"{u.scheme}://{u.netloc}{u.path}"
