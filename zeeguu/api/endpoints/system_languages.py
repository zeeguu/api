import json

from . import api
from zeeguu.api.utils.route_wrappers import cross_domain
from zeeguu.core.model import Language


@api.route("/system_languages", methods=["GET"])
@cross_domain
def system_languages():
    result = dict()
    result["learnable_languages"] = list(
        map((lambda x: dict(name=x.name, code=x.code)), Language.available_languages())
    )
    result["native_languages"] = list(
        map((lambda x: dict(name=x.name, code=x.code)), Language.native_languages())
    )
    return result


@api.route("/available_languages", methods=["GET"])
@cross_domain
def available_languages():
    """
    :return: jason with language codes for the
    supported languages.
    e.g. ["en", "fr", "de", "it", "no", "ro"]
    """
    available_language_codes = list(
        map((lambda x: x.code), Language.available_languages())
    )
    
    return json.dumps(available_language_codes)


@api.route("/available_native_languages", methods=["GET"])
@cross_domain
def available_native_languages():
    """
    :return: jason with language codes for the
    supported native languages. curently only english...
    e.g. ["en", "fr", "de", "it", "no", "ro"]unquote_plus(flask.r
    """
    available_language_codes = list(
        map((lambda x: x.code), Language.native_languages())
    )
    return json.dumps(available_language_codes)


@api.route("/ping", methods=["GET"])
def ping():
    return "OK"
