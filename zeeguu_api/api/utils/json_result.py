import json
import flask


def json_result(dictionary):
    js = json.dumps(dictionary)
    resp = flask.Response(js, status=200, mimetype="application/json")
    return resp
