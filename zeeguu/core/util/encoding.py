# -*- coding: utf8 -*-
import json
from datetime import timezone

from flask import make_response

from zeeguu.core.constants import JSON_TIME_FORMAT
from zeeguu.core.util.time import SERVER_TZ


class JSONSerializable(object):
    def serialize(self):
        raise NotImplementedError()


def _encoder(obj):
    if isinstance(obj, JSONSerializable):
        return obj.serialize()
    raise TypeError(repr(obj) + " is not JSON serializable")


def encode(obj):
    return json.dumps(obj, default=_encoder) + "\n"


def encode_error(code, error):
    return make_response(encode(error), code)


def datetime_to_json(naive_server_dt):
    """
    The one way this API puts a stored datetime on the wire.

    Every naive DateTime column in this DB is a clock reading in SERVER_TZ
    (see zeeguu/core/util/time.py). This converts one to UTC and emits it
    with an explicit "Z", which is what makes it safe for JS clients:
    `new Date("2026-08-25T12:34:56")` — no suffix — is parsed as the
    *browser's* local time, so a timestamp written seconds ago renders as
    hours ago for anyone not on UTC. The "Z" removes the ambiguity.

    Returns None for None, so call sites don't each need their own guard.
    """
    if naive_server_dt is None:
        return None
    return (
        naive_server_dt.replace(tzinfo=SERVER_TZ)
        .astimezone(timezone.utc)
        .strftime(JSON_TIME_FORMAT)
    )
