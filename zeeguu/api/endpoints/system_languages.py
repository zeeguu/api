import json

from . import api
from zeeguu.api.utils.route_wrappers import cross_domain
from zeeguu.core.model import Language
from zeeguu.core.audio_lessons.voice_config import voice_catalogue
from zeeguu.core.language.varieties import catalogue as variety_catalogue


@api.route("/system_languages", methods=["GET"])
@cross_domain
def system_languages():
    result = dict()
    # Which languages offer a regional variety, and what each is called. Served
    # from here so the client does not keep a second copy of a list that has to
    # agree with how the feeds are tagged.
    result["varieties"] = variety_catalogue()
    # The dialects a learner may choose, a shorter list than the one above:
    # French offers Belgium there and Google has no Belgian French voice. Gated on
    # the voices because the audio lesson is the only feature honouring a dialect
    # so far -- it widens when the translator and the LLM prompt read it too.
    result["dialects"] = voice_catalogue()
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
