import json
import os

from zeeguu.logging import log

from apimux.api_base import BaseThirdPartyAPIService
from apimux.mux import APIMultiplexer
from apimux.log import logger

from python_translators.config import get_key_from_config
from python_translators.translation_response import (
    TranslationResponse,
    order_by_quality,
    filter_empty_translations,
)
from python_translators.translation_response import merge_translations
from python_translators.factories.google_translator_factory import (
    GoogleTranslatorFactory,
)
from python_translators.factories.microsoft_translator_factory import (
    MicrosoftTranslatorFactory,
)
from python_translators.translators.wordnik_translator import WordnikTranslator

import logging


logging.getLogger("python_translators").setLevel(logging.CRITICAL)


MULTI_LANG_TRANSLATOR_AB_TESTING = False
if os.environ.get("MULTI_LANG_TRANSLATOR_AB_TESTING", None) is not None:
    logger.warning("A/B testing enabled! - MULTI_LANG_TRANSLATOR_AB_TESTING")
    MULTI_LANG_TRANSLATOR_AB_TESTING = True


class WordnikTranslate(BaseThirdPartyAPIService):
    def __init__(self, KEY_ENVVAR_NAME):
        super(WordnikTranslate, self).__init__(name=("Wordnik - %s" % KEY_ENVVAR_NAME))
        self._key_envvar_name = KEY_ENVVAR_NAME

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"],
        )
        lang_config["key"] = get_key_from_config(self._key_envvar_name)
        self._translator = WordnikTranslator(**lang_config)
        self._translator.quality = 90
        response = self._translator.translate(data["query"])
        if len(response.translations) == 0:
            return None
        return response


class GoogleTranslateWithContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(GoogleTranslateWithContext, self).__init__(name="Google - with context")

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"],
        )
        # Google Translator WITH context
        self._translator = GoogleTranslatorFactory.build_with_context(**lang_config)
        self._translator.quality = 95
        response = self._translator.translate(data["query"])
        if len(response.translations) == 0:
            return None
        return response


class GoogleTranslateWithoutContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(GoogleTranslateWithoutContext, self).__init__(
            name="Google - without context"
        )

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"],
        )
        # Google Translator WITHOUT context
        self._translator = GoogleTranslatorFactory.build_contextless(**lang_config)
        self._translator.quality = 70
        response = self._translator.translate(data["query"])
        if len(response.translations) == 0:
            return None
        return response


class MicrosoftTranslateWithContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(MicrosoftTranslateWithContext, self).__init__(
            name="Microsoft - with context"
        )

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"],
        )
        # Microsoft Translator WITH context
        self._translator = MicrosoftTranslatorFactory.build_with_context(**lang_config)
        self._translator.quality = 80
        response = self._translator.translate(data["query"])
        if len(response.translations) == 0:
            return None
        return response


class MicrosoftTranslateWithoutContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(MicrosoftTranslateWithoutContext, self).__init__(
            name="Microsoft - without context"
        )

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"],
        )
        # Microsoft Translator WITHOUT context
        self._translator = MicrosoftTranslatorFactory.build_contextless(**lang_config)
        self._translator.quality = 60
        response = self._translator.translate(data["query"])
        if len(response.translations) == 0:
            return None
        return response


api_mux_translators = APIMultiplexer(
    api_list=[
        GoogleTranslateWithContext(),
        GoogleTranslateWithoutContext(),
        MicrosoftTranslateWithContext(),
        MicrosoftTranslateWithoutContext(),
    ],
    config_filepath=os.environ.get("API_MUX_CONFIG__TRANSLATORS", ""),
)

wordnik_api_keys = []
for env_var_name in os.environ:
    if env_var_name.startswith("WORDNIK_API_KEY"):
        wordnik_api_keys += [env_var_name]
wordnik_translators = [WordnikTranslate(apikey) for apikey in wordnik_api_keys]
a_b_testing_wordnik = len(wordnik_translators) > 1
logger.info("Number of wordnik endpoints keys: %s" % len(wordnik_translators))
api_mux_worddefs = APIMultiplexer(
    api_list=wordnik_translators,
    config_filepath=os.environ.get("API_MUX_CONFIG__EN2EN", ""),
)


def get_all_translations(data):
    if data["from_lang_code"] == data["to_lang_code"] == "en":
        # Wordnik case, get only the top result
        response = get_next_results(data, number_of_results=1)
    else:
        response = get_next_results(data, number_of_results=-1)

    logger.debug(f"Zeeguu-API - Request data: {data}")
    return response


def get_next_results(
    data, exclude_services=[], exclude_results=[], number_of_results=-1
):
    translator_data = {
        "source_language": data["from_lang_code"],
        "target_language": data["to_lang_code"],
        "query": data["query"],
    }
    api_mux = None
    if data["from_lang_code"] == data["to_lang_code"] == "en":
        api_mux = api_mux_worddefs
    else:
        api_mux = api_mux_translators

    if number_of_results == 1:
        logger.debug("Getting only top result")
        translator_results = api_mux.get_next_results(
            translator_data, number_of_results=1
        )
    else:
        logger.debug("Getting all results")
        translator_results = api_mux.get_next_results(
            translator_data, number_of_results=-1, exclude_services=exclude_services
        )
    log(f"Got results get_next_results: {translator_results}")
    json_translator_results = [(x, y.to_json()) for x, y in translator_results]
    logger.debug(
        "get_next_results Zeeguu-API - Got results: %s" % json_translator_results
    )
    logger.debug("get_next_results - exclude_services %s" % exclude_services)
    # Returning data: [('GoogleTranslateWithContext',
    #                   <python_translators.translation_response.TranslationResponse>), ...]
    translations = []
    for service_name, translation in translator_results:
        if translation is None:
            continue
        lower_translation = translation.translations[0]["translation"].lower()
        if lower_translation in exclude_results:
            # Translation already exists fetched by get_top_translation
            continue
        translations = merge_translations(translations, translation.translations)

    translations = filter_empty_translations(translations)

    if not MULTI_LANG_TRANSLATOR_AB_TESTING:
        # Disabling order by quality when A/B testing is enabled
        translations = order_by_quality(translations, translator_data["query"])

    log(f"Translations get_next_results: {translations}")
    response = TranslationResponse(translations=translations)
    log(f"Returning response get_next_results: {response}")
    return response


def contribute_trans(data):
    logger.debug(
        "Preferred service: %s" % json.dumps(data, ensure_ascii=False).encode("utf-8")
    )
