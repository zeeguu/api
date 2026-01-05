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
    if response is None or not response.translations:
        return None
    t = response.translations[0]

    t["likelihood"] = t.pop("quality")
    t["source"] = t["service_name"]

    return t


@cache_on_data_keys("source_language", "target_language", "word", "context")
def microsoft_contextual_translate(data):
    gtx = MicrosoftTranslateWithContext()

    response = gtx.get_result(data)
    if response is None or not response.translations:
        return None
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
def translate_mwe_phrase(word, from_lang, to_lang):
    """
    Translate a Multi-Word Expression (MWE) as a standalone phrase.

    For MWEs like "vil have fjernet" (Danish future perfect), contextual translation
    can fail because the full sentence context leads to grammar misinterpretation.
    E.g., "Vi vil have fjernet momsen" → "We want to remove VAT" (wrong!)
    But "vil have fjernet" alone → "will have removed" (correct!)

    Google contextless handles grammatical MWEs better than contextual approaches.

    Args:
        word: The MWE phrase (e.g., "vil have fjernet", "kom op")
        from_lang: Source language code
        to_lang: Target language code

    Returns:
        dict with 'translation', 'source', 'likelihood' keys, or None
    """
    from python_translators.translation_query import TranslationQuery
    from python_translators.factories.google_translator_factory import GoogleTranslatorFactory

    try:
        # Use contextless translation for the phrase
        query = TranslationQuery(word, "", "", 1)

        translator = GoogleTranslatorFactory.build_contextless(
            source_language=from_lang,
            target_language=to_lang
        )
        translator.quality = 85  # Good quality for MWE phrases

        response = translator.translate(query)
        if response and response.translations:
            t = response.translations[0]
            return {
                "translation": t["translation"],
                "source": "Google - MWE phrase",
                "likelihood": t.get("quality", 85),
                "service_name": "Google - MWE phrase"
            }
    except Exception as e:
        log(f"MWE phrase translation failed: {e}")

    return None


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

    # For multi-word expressions, try phrase-only translation first
    # This handles grammatical MWEs better (e.g., Danish "vil have fjernet" = "will have removed")
    # Contextual translation can misinterpret grammar when full sentence is provided
    if " " in word:
        result = translate_mwe_phrase(word, from_lang, to_lang)
        if result:
            return result

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


def get_translations_streaming(word, context, from_lang, to_lang, is_separated_mwe=False, full_sentence_context=None):
    """
    Generator that yields translations as they arrive (for SSE streaming).

    Yields translation dicts one at a time, allowing frontend to display progressively.
    """
    from python_translators.translation_query import TranslationQuery
    from concurrent.futures import ThreadPoolExecutor, as_completed

    seen_translations = set()

    def yield_if_new(t):
        """Yield translation if not a duplicate."""
        if t is None:
            return None
        text = t.get("translation", "").lower().strip()
        if text and text not in seen_translations:
            seen_translations.add(text)
            return t
        return None

    # For contiguous MWEs (words with spaces)
    if " " in word and not is_separated_mwe:
        # First yield the phrase translation (fast and reliable)
        t_mwe = translate_mwe_phrase(word, from_lang, to_lang)
        if t_mwe:
            result = yield_if_new(t_mwe)
            if result:
                yield result

        # Then try other services in parallel - they might give different results
        # Also include LLM for contextual alternatives
        funcs = [
            lambda: azure_alignment_contextual_translate({
                "source_language": from_lang,
                "target_language": to_lang,
                "word": word,
                "query": TranslationQuery(word, "", "", 1),
                "context": context,
            }),
            lambda: microsoft_contextual_translate({
                "source_language": from_lang,
                "target_language": to_lang,
                "word": word,
                "query": TranslationQuery(word, "", "", 1),
                "context": context,
            }),
            lambda: google_contextual_translate({
                "source_language": from_lang,
                "target_language": to_lang,
                "word": word,
                "query": TranslationQuery(word, "", "", 1),
                "context": context,
            }),
            lambda: translate_with_llm(word, context, from_lang, to_lang),
        ]

        with ThreadPoolExecutor(max_workers=len(funcs)) as executor:
            futures = {executor.submit(f): i for i, f in enumerate(funcs)}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    t = yield_if_new(result)
                    if t:
                        yield t
                except Exception:
                    pass
        return

    # For separated MWEs
    if is_separated_mwe and full_sentence_context:
        funcs = [
            lambda: translate_separated_mwe(word, full_sentence_context, from_lang, to_lang),
            lambda: translate_with_llm(word, full_sentence_context, from_lang, to_lang),
        ]
    else:
        # Single words: use all contextual services
        try:
            query = TranslationQuery.for_word_occurrence(word, context, 1, 7)
        except (AttributeError, Exception):
            query = TranslationQuery(word, "", "", 1)

        data = {
            "source_language": from_lang,
            "target_language": to_lang,
            "word": word,
            "query": query,
            "context": context,
        }
        funcs = [
            lambda d=data: azure_alignment_contextual_translate(d),
            lambda d=data: microsoft_contextual_translate(d),
            lambda d=data: google_contextual_translate(d),
        ]

    # Run in parallel and yield as they complete
    with ThreadPoolExecutor(max_workers=len(funcs)) as executor:
        futures = {executor.submit(f): i for i, f in enumerate(funcs)}
        for future in as_completed(futures):
            try:
                result = future.result()
                t = yield_if_new(result)
                if t:
                    yield t
            except Exception:
                pass


def _remove_duplicate_translations(translations):
    """
    Remove duplicate translations, keeping the first occurrence.
    Duplicates are determined by lowercase translation text.
    """
    seen = set()
    unique = []
    for t in translations:
        if t is None:
            continue
        text = t.get("translation", "").lower().strip()
        if text and text not in seen:
            seen.add(text)
            unique.append(t)
    return unique


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
        List of translation dicts (duplicates removed)
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
        return _remove_duplicate_translations([t0, t1, t2, t3])
    else:
        # For contiguous MWEs: use phrase translation plus other services and LLM
        if " " in word:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            query = TranslationQuery(word, "", "", 1)
            data = {
                "source_language": from_lang,
                "target_language": to_lang,
                "word": word,
                "query": query,
                "context": context,
            }

            funcs = [
                lambda: translate_mwe_phrase(word, from_lang, to_lang),
                lambda d=data: azure_alignment_contextual_translate(d),
                lambda d=data: microsoft_contextual_translate(d),
                lambda d=data: google_contextual_translate(d),
                lambda: translate_with_llm(word, context, from_lang, to_lang),
            ]

            results = []
            with ThreadPoolExecutor(max_workers=len(funcs)) as executor:
                futures = [executor.submit(f) for f in funcs]
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception:
                        pass

            return _remove_duplicate_translations(results)

        # Single words: use all contextual services (in parallel)
        try:
            query = TranslationQuery.for_word_occurrence(word, context, 1, 7)
        except (AttributeError, Exception):
            # Word not found in context or regex failed (special chars like "-")
            # Fall back to simple query
            query = TranslationQuery(word, "", "", 1)
        data = {
            "source_language": from_lang,
            "target_language": to_lang,
            "word": word,
            "query": query,
            "context": context,
        }

        # Run translation services in parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def get_azure():
            return azure_alignment_contextual_translate(data)

        def get_msft():
            return microsoft_contextual_translate(data)

        def get_google():
            return google_contextual_translate(data)

        results = {"azure": None, "msft": None, "google": None}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(get_azure): "azure",
                executor.submit(get_msft): "msft",
                executor.submit(get_google): "google",
            }
            for future in as_completed(futures):
                key = futures[future]
                try:
                    results[key] = future.result()
                except Exception:
                    pass

        # Romanian: Azure alignment confuses "a" (perfect tense auxiliary) with "the"
        if from_lang == "ro":
            return _remove_duplicate_translations([results["google"], results["msft"], results["azure"]])
        else:
            return _remove_duplicate_translations([results["azure"], results["msft"], results["google"]])
