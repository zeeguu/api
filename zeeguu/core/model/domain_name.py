import re

import sqlalchemy
from sqlalchemy.orm.exc import NoResultFound
import time

import logging

import zeeguu.core

from zeeguu.core.model import db


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
        try:
            return cls.find(_domain)
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            # except:
            try:
                new = cls(_domain)
                session.add(new)
                session.commit()
                return new
            except sqlalchemy.exc.IntegrityError or sqlalchemy.exc.DatabaseError:
                # except:
                for i in range(10):
                    try:
                        session.rollback()
                        d = cls.find(_domain)
                        logging.info("found domain after recovering from race")
                        return d
                    except:
                        logging.info("exception of second degree in domain..." + str(i))
                        time.sleep(0.1)
                        continue
                    break
