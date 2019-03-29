import zeeguu_core

from apimux.api_base import BaseThirdPartyAPIService
from apimux.mux import APIMultiplexer

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


class WordnikTranslate(BaseThirdPartyAPIService):
    def __init__(self):
        super(WordnikTranslate, self).__init__()

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"]
        )
        lang_config['key'] = get_key_from_config('WORDNIK_API_KEY')
        self._translator = WordnikTranslator(**lang_config)
        self._translator.quality = 90
        return self._translator.translate(data["query"])


class GoogleTranslateWithContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(GoogleTranslateWithContext, self).__init__()

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"]
        )
        # Google Translator WITH context
        self._translator = GoogleTranslatorFactory.build_with_context(
            **lang_config)
        self._translator.quality = 95
        return self._translator.translate(data["query"])


class GoogleTranslateWithoutContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(GoogleTranslateWithoutContext, self).__init__()

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"]
        )
        # Google Translator WITHOUT context
        self._translator = GoogleTranslatorFactory.build_contextless(
            **lang_config)
        self._translator.quality = 70
        return self._translator.translate(data["query"])


class MicrosoftTranslateWithContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(MicrosoftTranslateWithContext, self).__init__()

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"]
        )
        # Microsoft Translator WITH context
        self._translator = MicrosoftTranslatorFactory.build_with_context(
            **lang_config)
        self._translator.quality = 80
        return self._translator.translate(data["query"])


class MicrosoftTranslateWithoutContext(BaseThirdPartyAPIService):
    def __init__(self):
        super(MicrosoftTranslateWithoutContext, self).__init__()

    def get_result(self, data):
        lang_config = dict(
            source_language=data["source_language"],
            target_language=data["target_language"]
        )
        # Microsoft Translator WITHOUT context
        self._translator = MicrosoftTranslatorFactory.build_contextless(
            **lang_config)
        self._translator.quality = 60
        return self._translator.translate(data["query"])


api_mux_translators = APIMultiplexer(api_list=[
    GoogleTranslateWithContext(), GoogleTranslateWithoutContext(),
    MicrosoftTranslateWithContext(), MicrosoftTranslateWithoutContext()])
api_mux_worddefs = APIMultiplexer(api_list=[WordnikTranslate()])


def get_all_translations(data):
    translator_data = {
        "source_language": data["from_lang_code"],
        "target_language": data["to_lang_code"],
        "query": data["query"]
    }
    api_mux_to_use = None
    if data["from_lang_code"] == data["to_lang_code"] == "en":
        api_mux_to_use = api_mux_worddefs
    else:
        api_mux_to_use = api_mux_translators
    translator_results = api_mux_to_use.get_all_results(translator_data)
    zeeguu_core.log(f"Got results: {translator_results}")
    # Returning data: [('GoogleTranslateWithContext',
    #                   <python_translators.translation_response.TranslationResponse>), ...]
    translations = []
    for service_name, translation in translator_results:
        if translation is None:
            continue
        translations = merge_translations(translations,
                                          translation.translations)

    translations = filter_empty_translations(translations)
    translations = order_by_quality(translations, data["query"])

    zeeguu_core.log(f"Translations: {translations}")
    response = TranslationResponse(translations=translations)
    zeeguu_core.log(f"Returning response: {response}")
    return response


def minimize_context(context_str, from_lang_code, word_str):
    _query = TranslationQuery.for_word_occurrence(word_str, context_str, 1, 7)
    processor = RemoveUnnecessarySentences(from_lang_code)
    query = processor.process_query(_query)
    minimal_context = (
        query.before_context + ' ' + query.query + query.after_context)
    return minimal_context, query
