"""
Benchmark: Microsoft + Alignment vs Stanza MWE + Google

Compares two approaches for MWE-aware translation:
1. Microsoft sentence translation with alignment (MWE detection from alignment)
2. Stanza MWE detection + Google word/phrase translation

Run with: source ~/.venvs/z_env/bin/activate && python -m tools._benchmark_translation
"""

import os
import time
import requests
from statistics import mean, stdev

# Microsoft Translator API
MICROSOFT_KEY = os.environ.get("MICROSOFT_TRANSLATE_API_KEY")
MICROSOFT_REGION = os.environ.get("MICROSOFT_TRANSLATE_REGION", "westeurope")
MICROSOFT_ENDPOINT = "https://api.cognitive.microsofttranslator.com"

# Test sentences with particle verbs / idioms
# (sentence, clicked_word, expected_mwe, source_lang, target_lang)
TEST_CASES = [
    ("Han kom op med en god idé", "op", "kom op", "da", "en"),  # Danish particle verb
    ("Ich rufe dich morgen an", "an", "rufe an", "de", "en"),  # German separable verb
]

# Stanza models - only test languages we have models for
STANZA_LANGS = {"da", "de"}


def microsoft_translate_with_alignment(text, from_lang, to_lang):
    """Call Microsoft Translator API with alignment using Azure SDK"""
    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.ai.translation.text import TextTranslationClient
    except ImportError:
        return None, None, "Azure SDK not installed"

    if not MICROSOFT_KEY:
        return None, None, "No API key"

    # Initialize client (cached for performance)
    if not hasattr(microsoft_translate_with_alignment, 'client'):
        credential = AzureKeyCredential(MICROSOFT_KEY)
        microsoft_translate_with_alignment.client = TextTranslationClient(credential=credential)

    client = microsoft_translate_with_alignment.client

    start = time.perf_counter()
    try:
        response = client.translate(
            body=[text],
            to_language=[to_lang],
            from_language=from_lang,
            include_alignment=True,
        )
        elapsed = (time.perf_counter() - start) * 1000  # ms

        if response and len(response) > 0:
            result = response[0]
            trans = result.translations[0]
            translation = trans.text
            alignment_str = trans.alignment.proj if trans.alignment else ""
            return {"translation": translation, "alignment": alignment_str}, elapsed, None
        return None, elapsed, "No response"

    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return None, elapsed, f"Error: {e}"


class SimpleToken:
    """Simple token class matching the interface expected by mwe_detector"""
    def __init__(self, text, dep, head, lemma):
        self.text = text
        self.dep = dep
        self.head = head
        self.lemma = lemma


def stanza_mwe_detection(text, lang):
    """Detect MWEs using Stanza dependency parsing"""
    try:
        import stanza
        from zeeguu.core.mwe.detector import detect_particle_verbs
    except ImportError as e:
        return None, 0, f"Import error: {e}"

    start = time.perf_counter()

    # Get or create Stanza pipeline
    if not hasattr(stanza_mwe_detection, 'pipelines'):
        stanza_mwe_detection.pipelines = {}

    if lang not in stanza_mwe_detection.pipelines:
        stanza_mwe_detection.pipelines[lang] = stanza.Pipeline(
            lang=lang,
            processors='tokenize,pos,lemma,depparse',
            verbose=False
        )

    nlp = stanza_mwe_detection.pipelines[lang]
    doc = nlp(text)

    # Convert to our token format and detect MWEs
    tokens = []
    for sent in doc.sentences:
        for word in sent.words:
            tokens.append(SimpleToken(
                text=word.text,
                dep=word.deprel,
                head=word.head,
                lemma=word.lemma,
            ))

    mwes = detect_particle_verbs(tokens)
    elapsed = (time.perf_counter() - start) * 1000

    return mwes, elapsed, None


def google_translate_phrase(phrase, context, from_lang, to_lang):
    """Translate a phrase using Google"""
    try:
        from python_translators.factories.google_translator_factory import GoogleTranslatorFactory
        from python_translators.translation_query import TranslationQuery
    except ImportError as e:
        return None, 0, f"Import error: {e}"

    lang_config = {
        "source_language": from_lang,
        "target_language": to_lang,
    }
    translator = GoogleTranslatorFactory.build_with_context(**lang_config)

    # Use context for word occurrence, or fall back to contextless
    if context and phrase in context:
        query = TranslationQuery.for_word_occurrence(phrase, context, 1, 7)
    else:
        query = TranslationQuery.for_word_occurrence(phrase, phrase, 1, 1)

    start = time.perf_counter()
    response = translator.translate(query)
    elapsed = (time.perf_counter() - start) * 1000

    if response and response.translations:
        return response.translations[0], elapsed, None
    return None, elapsed, "No translation"


def run_benchmark():
    print("=" * 70)
    print("Benchmark: Microsoft+Alignment vs Stanza+Google")
    print("=" * 70)

    if not MICROSOFT_KEY:
        print("\nWARNING: MICROSOFT_TRANSLATE_API_KEY not set")
        print("Microsoft benchmarks will fail.\n")

    # Check Stanza availability
    try:
        import stanza
        print("Stanza: Available")
    except ImportError:
        print("Stanza: NOT AVAILABLE - install with: pip install stanza")
        return

    # Check MWE detector
    try:
        from zeeguu.core.mwe.detector import detect_particle_verbs
        print("MWE Detector: Available")
    except ImportError:
        print("MWE Detector: NOT AVAILABLE")
        return

    ms_times = []
    stanza_times = []
    google_times = []

    print("\n" + "-" * 70)
    print("Warming up Stanza models (first load is slow)...")
    for lang in STANZA_LANGS:
        stanza_mwe_detection("Test", lang)
    print("Warm-up complete.")
    print("-" * 70)

    for sentence, word, expected_mwe, src, tgt in TEST_CASES:
        if src not in STANZA_LANGS:
            print(f"\nSkipping {src} - no Stanza model")
            continue

        print(f"\n{'='*70}")
        print(f"Sentence: '{sentence}'")
        print(f"Clicked: '{word}' | Expected MWE: '{expected_mwe}'")
        print(f"{'='*70}")

        # Approach 1: Microsoft with alignment
        print("\n[Microsoft + Alignment]")
        result, ms_time, err = microsoft_translate_with_alignment(sentence, src, tgt)
        if err:
            print(f"  Error: {err}")
        else:
            ms_times.append(ms_time)
            print(f"  Translation: '{result['translation']}'")
            print(f"  Alignment: {result['alignment']}")
            print(f"  Time: {ms_time:.0f}ms")

        # Approach 2: Stanza MWE + Google
        print("\n[Stanza MWE + Google]")
        mwes, stanza_time, err = stanza_mwe_detection(sentence, src)
        if err:
            print(f"  Stanza Error: {err}")
        else:
            stanza_times.append(stanza_time)
            print(f"  MWEs detected: {mwes}")
            print(f"  Stanza time: {stanza_time:.0f}ms")

            # Translate the MWE (or word if no MWE)
            phrase_to_translate = expected_mwe  # In real code, we'd extract from MWEs
            result, g_time, err = google_translate_phrase(phrase_to_translate, sentence, src, tgt)
            if err:
                print(f"  Google Error: {err}")
            else:
                google_times.append(g_time)
                print(f"  Google translation of '{phrase_to_translate}': '{result.get('translation', 'N/A')}'")
                print(f"  Google time: {g_time:.0f}ms")
                print(f"  Total Stanza+Google: {stanza_time + g_time:.0f}ms")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if ms_times:
        print(f"\nMicrosoft + Alignment:")
        print(f"  Mean: {mean(ms_times):.0f}ms")
        if len(ms_times) > 1:
            print(f"  Stdev: {stdev(ms_times):.0f}ms")

    if stanza_times and google_times:
        combined = [s + g for s, g in zip(stanza_times, google_times)]
        print(f"\nStanza MWE + Google:")
        print(f"  Stanza mean: {mean(stanza_times):.0f}ms")
        print(f"  Google mean: {mean(google_times):.0f}ms")
        print(f"  Combined mean: {mean(combined):.0f}ms")

    if ms_times and stanza_times and google_times:
        combined_mean = mean(stanza_times) + mean(google_times)
        diff = mean(ms_times) - combined_mean
        print(f"\nDifference: Microsoft is {abs(diff):.0f}ms {'faster' if diff < 0 else 'slower'}")


def check_language_support():
    """Check which Zeeguu languages Microsoft supports"""
    print("=" * 70)
    print("MICROSOFT TRANSLATOR - LANGUAGE SUPPORT")
    print("=" * 70)

    # Get supported languages (no auth needed)
    url = f"{MICROSOFT_ENDPOINT}/languages?api-version=3.0&scope=translation"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Error fetching languages: {response.status_code}")
        return

    ms_languages = set(response.json().get("translation", {}).keys())

    # Zeeguu's learnable languages
    zeeguu_learnable = ["de", "es", "fr", "nl", "en", "it", "da", "pl", "sv", "ru", "no", "hu", "pt", "ro", "el"]
    zeeguu_native = ["da", "en", "fr", "nl", "pl", "ro", "zh-CN", "tr", "ku", "ar", "so", "de", "sv", "sq", "es", "it", "ja", "sr", "pt", "ru", "uk", "vi", "hu", "lv", "ind", "ur", "ta", "bn", "el"]

    print(f"\nMicrosoft supports {len(ms_languages)} languages")

    print("\nZeeguu LEARNABLE languages (all must be supported):")
    all_supported = True
    for lang in sorted(zeeguu_learnable):
        check_lang = "nb" if lang == "no" else lang
        supported = check_lang in ms_languages
        icon = "✓" if supported else "✗"
        print(f"  {icon} {lang}")
        if not supported:
            all_supported = False

    print(f"\n{'All learnable languages supported!' if all_supported else 'Some languages NOT supported!'}")

    # Check native languages that might be missing
    missing_native = []
    for lang in zeeguu_native:
        check_lang = "nb" if lang == "no" else lang
        check_lang = "zh-Hans" if lang == "zh-CN" else check_lang
        check_lang = "id" if lang == "ind" else check_lang
        if check_lang not in ms_languages:
            missing_native.append(lang)

    if missing_native:
        print(f"\nNative languages NOT supported: {', '.join(missing_native)}")
    else:
        print("\nAll native languages supported!")


if __name__ == "__main__":
    check_language_support()
    print()
    run_benchmark()
