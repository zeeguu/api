from sqlalchemy import text

from zeeguu.core.model import db


def date_format(date_object):
    return date_object.strftime("%Y-%m-%d")


def datetime_format(date_object):
    return date_object.strftime("%Y-%m-%d %H:%M:%S")


def list_of_dicts_from_query(query, values):
    rows = db.session.execute(text(query), values)

    result = []
    for row in rows:
        result.append(dict(row._mapping))
    return result
