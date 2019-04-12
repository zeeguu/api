import json
import os

import zeeguu_core

from apimux.api_base import BaseThirdPartyAPIService
from apimux.mux import APIMultiplexer
from apimux.log import logger

from python_translators.config import get_key_from_config
from python_translators.query_processors.remove_unnecessary_sentences import (
    RemoveUnnecessarySentences)
from python_translators.translation_query import TranslationQuery
from python_translators.translation_response import (
    TranslationResponse, order_by_quality, filter_empty_translations)
from python_translators.translation_response import merge_translations
from python_translators.factories.google_translator_factory import (
    GoogleTranslatorFactory)
from python_translators.factories.microsoft_translator_factory import (
    MicrosoftTranslatorFactory)
from python_translators.translators.wordnik_translator import WordnikTranslator

MULTI_LANG_TRANSLATOR_AB_TESTING = False
if os.environ.get("MULTI_LANG_TRANSLATOR_AB_TESTING", None) is not None:
    logger.warning("A/B testing enabled! - MULTI_LANG_TRANSLATOR_AB_TESTING")
    MULTI_LANG_TRANSLATOR_AB_TESTING = True


class WordnikTranslate(BaseThirdPartyAPIService):
    def __init__(self, KEY_ENVVAR_NAME):
        super(WordnikTranslate, self).__init__(
            name=('Wordnik - %s' % KEY_ENVVAR_NAME))
        self._key_envvar_name = KEY_ENVVAR_NAME

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"]
        )
        lang_config['key'] = get_key_from_config(self._key_envvar_name)
        self._translator = WordnikTranslator(**lang_config)
        self._translator.quality = 90
        response = self._translator.translate(data["query"])
        if len(response.translations) == 0:
            return None
        return response


class GoogleTranslateWithContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(GoogleTranslateWithContext, self).__init__(
            name='Google - with context')

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"]
        )
        # Google Translator WITH context
        self._translator = GoogleTranslatorFactory.build_with_context(
            **lang_config)
        self._translator.quality = 95
        response = self._translator.translate(data["query"])
        if len(response.translations) == 0:
            return None
        return response


class GoogleTranslateWithoutContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(GoogleTranslateWithoutContext, self).__init__(
            name='Google - without context')

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"]
        )
        # Google Translator WITHOUT context
        self._translator = GoogleTranslatorFactory.build_contextless(
            **lang_config)
        self._translator.quality = 70
        response = self._translator.translate(data["query"])
        if len(response.translations) == 0:
            return None
        return response


class MicrosoftTranslateWithContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(MicrosoftTranslateWithContext, self).__init__(
            name='Microsoft - with context')

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"]
        )
        # Microsoft Translator WITH context
        self._translator = MicrosoftTranslatorFactory.build_with_context(
            **lang_config)
        self._translator.quality = 80
        response = self._translator.translate(data["query"])
        if len(response.translations) == 0:
            return None
        return response


class MicrosoftTranslateWithoutContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(MicrosoftTranslateWithoutContext, self).__init__(
            name='Microsoft - without context')

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"]
        )
        # Microsoft Translator WITHOUT context
        self._translator = MicrosoftTranslatorFactory.build_contextless(
            **lang_config)
        self._translator.quality = 60
        response = self._translator.translate(data["query"])
        if len(response.translations) == 0:
            return None
        return response


api_mux_translators = APIMultiplexer(api_list=[
    GoogleTranslateWithContext(), GoogleTranslateWithoutContext(),
    MicrosoftTranslateWithContext(), MicrosoftTranslateWithoutContext()],
    a_b_testing=MULTI_LANG_TRANSLATOR_AB_TESTING)


wordnik_api_keys = []
for env_var_name in os.environ:
    if env_var_name.startswith('WORDNIK_API_KEY'):
        wordnik_api_keys += [env_var_name]
wordnik_translators = [WordnikTranslate(apikey) for apikey in wordnik_api_keys]
a_b_testing_wordnik = len(wordnik_translators) > 1
logger.info("Number of wordnik api keys: %s" % len(wordnik_translators))
api_mux_worddefs = APIMultiplexer(
    api_list=wordnik_translators,
    a_b_testing=a_b_testing_wordnik)


def get_all_translations(data):
    translator_data = {
        "source_language": data["from_lang_code"],
        "target_language": data["to_lang_code"],
        "query": data["query"]
    }
    if data["from_lang_code"] == data["to_lang_code"] == "en":
        translator_results = api_mux_worddefs.get_top_result(translator_data)
    else:
        translator_results = api_mux_translators.get_all_results(
            translator_data)
    zeeguu_core.log(f"Got results: {translator_results}")
    json_translator_results = [(x, y.to_json()) for x, y in translator_results]
    logger.debug(f"Zeeguu-API - Request data: {data}")
    logger.debug(f"Zeeguu-API - Got results: {json_translator_results}")
    # Returning data: [('GoogleTranslateWithContext',
    #                   <python_translators.translation_response.TranslationResponse>), ...]
    translations = []
    for service_name, translation in translator_results:
        if translation is None:
            continue
        translations = merge_translations(translations,
                                          translation.translations)

    translations = filter_empty_translations(translations)
    if MULTI_LANG_TRANSLATOR_AB_TESTING:
        # Disabling order by quality when A/B testing is enabled
        translations = order_by_quality(translations, data["query"])

    zeeguu_core.log(f"Translations: {translations}")
    response = TranslationResponse(translations=translations)
    zeeguu_core.log(f"Returning response: {response}")
    return response


def contribute_trans(data):
    logger.debug("Preferred service: %s"
                 % json.dumps(data, ensure_ascii=False).encode('utf-8'))


def minimize_context(context_str, from_lang_code, word_str):
    _query = TranslationQuery.for_word_occurrence(word_str, context_str, 1, 7)
    processor = RemoveUnnecessarySentences(from_lang_code)
    query = processor.process_query(_query)
    minimal_context = (
        query.before_context + ' ' + query.query + query.after_context)
    return minimal_context, query
