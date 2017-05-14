import json

from . import api
from .utils.route_wrappers import cross_domain
from zeeguu.model import Language


@api.route("/available_languages", methods=["GET"])
@cross_domain
def available_languages():
    """
    :return: jason with language codes for the
    supported languages.
    e.g. ["en", "fr", "de", "it", "no", "ro"]
    """
    available_language_codes = list(map((lambda x: x.id), Language.available_languages()))
    return json.dumps(available_language_codes)


@api.route("/available_native_languages", methods=["GET"])
@cross_domain
def available_native_languages():
    """
    :return: jason with language codes for the
    supported native languages. curently only english...
    e.g. ["en", "fr", "de", "it", "no", "ro"]unquote_plus(flask.r
    """
    available_language_codes = list(map((lambda x: x.id), Language.native_languages()))
    return json.dumps(available_language_codes)
