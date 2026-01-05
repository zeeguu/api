import decimal
import json
from datetime import datetime, date

import flask


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):

        if isinstance(o, datetime):
            # e.g. "2021-04-26T18:51:47"
            return o.isoformat()

        if isinstance(o, decimal.Decimal):
            return int(o)

        return json.JSONEncoder.default(self, o)


def json_result(dictionary, status=200):
    stringified = json.dumps(dictionary, cls=DateTimeEncoder)
    resp = flask.Response(stringified, status=status, mimetype="application/json")
    return resp
