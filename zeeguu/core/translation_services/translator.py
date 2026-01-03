import json
import os
from functools import lru_cache

from zeeguu.api.utils.caching_decorator import cache_on_data_keys
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
ab_testing_config = os.environ.get("MULTI_LANG_TRANSLATOR_AB_TESTING", None)
if ab_testing_config is not None:
    MULTI_LANG_TRANSLATOR_AB_TESTING = ab_testing_config == "True"
    logger.warning(
        f"MULTILANG_TRANSLATOR_AB_TESTING: {MULTI_LANG_TRANSLATOR_AB_TESTING}"
    )


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


@cache_on_data_keys("source_language", "target_language", "word", "context")
def google_contextual_translate(data):
    gtx = GoogleTranslateWithContext()

    response = gtx.get_result(data)
    t = response.translations[0]

    t["likelihood"] = t.pop("quality")
    t["source"] = t["service_name"]

    return t


@cache_on_data_keys("source_language", "target_language", "word", "context")
def microsoft_contextual_translate(data):
    gtx = MicrosoftTranslateWithContext()

    response = gtx.get_result(data)
    t = response.translations[0]

    t["likelihood"] = t.pop("quality")
    t["source"] = t["service_name"]

    return t


@cache_on_data_keys("source_language", "target_language", "word", "context")
def azure_alignment_contextual_translate(data):
    """
    Translate using Azure's word alignment feature.

    This is more reliable than the span-tag approach because it uses
    explicit word-to-word mappings rather than hoping the translation
    API preserves tag positions.
    """
    from zeeguu.core.translation_services.azure_alignment import azure_alignment_translate

    result = azure_alignment_translate(data)
    if result:
        # Ensure consistent key naming
        result["likelihood"] = result.get("likelihood", 90)
        result["source"] = result.get("source", "Microsoft - alignment")
    return result


@lru_cache(maxsize=1000)
def translate_in_context(word, context, from_lang, to_lang):
    """
    Translate a word or adjacent MWE using context.

    This is the standard translation path for:
    - Single words: "altså"
    - Adjacent MWEs: "kom op", "il y a"

    Uses Azure alignment (most reliable), falls back to Microsoft/Google span-tag.

    Returns:
        dict with 'translation', 'source', 'likelihood' keys, or None
    """
    from python_translators.translation_query import TranslationQuery

    try:
        query = TranslationQuery.for_word_occurrence(word, context, 1, 7)
    except AttributeError:
        query = TranslationQuery(word, "", "", 1)

    data = {
        "source_language": from_lang,
        "target_language": to_lang,
        "word": word,
        "query": query,
        "context": context,
    }

    result = azure_alignment_contextual_translate(data)
    if not result:
        result = microsoft_contextual_translate(data)
    if not result:
        result = google_contextual_translate(data)

    return result


@lru_cache(maxsize=1000)
def translate_separated_mwe(word, sentence, from_lang, to_lang):
    """
    Translate a separated MWE like "rufe ... an".

    For particle verbs where the parts aren't adjacent in the sentence,
    uses Azure alignment to find and translate each part separately.

    Args:
        word: The MWE with parts joined by " ... " (e.g., "rufe ... an")
        sentence: The full sentence containing the MWE
        from_lang: Source language code
        to_lang: Target language code

    Returns:
        dict with 'translation', 'source', 'likelihood' keys, or None
    """
    from python_translators.translation_query import TranslationQuery

    query = TranslationQuery(word, "", "", 1)

    data = {
        "source_language": from_lang,
        "target_language": to_lang,
        "word": word,
        "query": query,
        "context": sentence,
    }

    result = azure_alignment_contextual_translate(data)
    if not result:
        result = microsoft_contextual_translate(data)
    if not result:
        result = google_contextual_translate(data)

    return result


@lru_cache(maxsize=1000)
def translate_with_llm(word, sentence, from_lang, to_lang):
    """
    Translate a word or MWE using an LLM.

    Useful for separated MWEs where the LLM understands grammar better.

    Args:
        word: The word/MWE to translate (e.g., "rufe ... an")
        sentence: The sentence containing the word
        from_lang: Source language code
        to_lang: Target language code

    Returns:
        dict with 'translation', 'source', 'likelihood' keys, or None
    """
    try:
        from zeeguu.core.llm_services.mwe_translation_service import translate_separated_mwe as llm_translate

        translation = llm_translate(word, sentence, from_lang, to_lang)

        if translation:
            return {
                "translation": translation,
                "source": "LLM",
                "likelihood": 85,
            }
    except Exception as e:
        log(f"LLM translation failed: {e}")

    return None


def get_best_translation(word, context, from_lang, to_lang, is_separated_mwe=False, full_sentence_context=None):
    """
    Get the best translation for a word or MWE.

    Args:
        word: Word to translate
        context: Sentence context (may be truncated to ~28 words)
        from_lang: Source language code
        to_lang: Target language code
        is_separated_mwe: True if word is a separated MWE like "rufe ... an"
        full_sentence_context: Full untruncated sentence for separated MWEs

    Returns:
        dict with 'translation', 'source', 'likelihood' keys, or None
    """
    if is_separated_mwe and full_sentence_context:
        return translate_separated_mwe(word, full_sentence_context, from_lang, to_lang)
    else:
        return translate_in_context(word, context, from_lang, to_lang)


def get_all_translations(word, context, from_lang, to_lang, is_separated_mwe=False, full_sentence_context=None):
    """
    Get translations from all available services.

    Args:
        word: Word to translate
        context: Sentence context (may be truncated to ~28 words)
        from_lang: Source language code
        to_lang: Target language code
        is_separated_mwe: True if word is a separated MWE like "rufe ... an"
        full_sentence_context: Full untruncated sentence for separated MWEs

    Returns:
        List of translation dicts
    """
    from python_translators.translation_query import TranslationQuery

    if is_separated_mwe and full_sentence_context:
        # Azure alignment finds each part separately
        t0 = translate_separated_mwe(word, full_sentence_context, from_lang, to_lang)
        # LLM understands grammar well
        t1 = translate_with_llm(word, full_sentence_context, from_lang, to_lang)
        # Context-free fallbacks
        query = TranslationQuery(word, "", "", 1)
        data = {
            "source_language": from_lang,
            "target_language": to_lang,
            "word": word,
            "query": query,
            "context": "",
        }
        t2 = microsoft_contextual_translate(data)
        t3 = google_contextual_translate(data)
        return [t for t in [t0, t1, t2, t3] if t]
    else:
        # All services with context
        query = TranslationQuery.for_word_occurrence(word, context, 1, 7)
        data = {
            "source_language": from_lang,
            "target_language": to_lang,
            "word": word,
            "query": query,
            "context": context,
        }
        t_azure = azure_alignment_contextual_translate(data)
        t_msft = microsoft_contextual_translate(data)
        t_google = google_contextual_translate(data)

        # Language-specific ordering
        # Romanian: Azure alignment confuses "a" (perfect tense auxiliary) with "the"
        # TODO: May need to generalize this for other languages with similar issues
        if from_lang == "ro":
            return [t for t in [t_google, t_msft, t_azure] if t]
        else:
            return [t for t in [t_azure, t_msft, t_google] if t]
