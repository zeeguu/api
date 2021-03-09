# -*- coding: utf8 -*-
import json

from flask import make_response


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
