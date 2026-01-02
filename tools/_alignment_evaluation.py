"""
Comprehensive evaluation of Microsoft Translator alignment for MWE detection.

Tests 20 German and 20 Danish examples to identify where alignment works/fails.

Run with:
  source ~/.venvs/z_env/bin/activate && \
  MICROSOFT_TRANSLATE_API_KEY="..." python -m tools._alignment_evaluation
"""

import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text import TextTranslationClient

MICROSOFT_KEY = os.environ.get("MICROSOFT_TRANSLATE_API_KEY")

# German test cases: (sentence, mwe_words, mwe_type, expected_behavior)
# mwe_words = list of words that should be detected as belonging together
GERMAN_EXAMPLES = [
    # Separable verbs (Trennbare Verben)
    ("Ich rufe dich morgen an", ["rufe", "an"], "separable_verb", "anrufen"),
    ("Er steht jeden Tag früh auf", ["steht", "auf"], "separable_verb", "aufstehen"),
    ("Sie gibt niemals auf", ["gibt", "auf"], "separable_verb", "aufgeben"),
    ("Wir fangen morgen an", ["fangen", "an"], "separable_verb", "anfangen"),
    ("Er kommt heute Abend zurück", ["kommt", "zurück"], "separable_verb", "zurückkommen"),
    ("Sie bringt ihre Freundin mit", ["bringt", "mit"], "separable_verb", "mitbringen"),
    ("Ich schaue mir den Film an", ["schaue", "an"], "separable_verb", "anschauen"),
    ("Er macht das Licht aus", ["macht", "aus"], "separable_verb", "ausmachen"),
    ("Sie zieht sich warm an", ["zieht", "an"], "separable_verb", "anziehen"),
    ("Wir laden alle Freunde ein", ["laden", "ein"], "separable_verb", "einladen"),

    # Idioms
    ("Das ist mir Wurst", ["ist", "mir", "Wurst"], "idiom", "I don't care"),
    ("Er hat einen Vogel", ["hat", "einen", "Vogel"], "idiom", "he's crazy"),
    ("Ich drücke dir die Daumen", ["drücke", "die", "Daumen"], "idiom", "fingers crossed"),
    ("Das geht mir auf den Keks", ["geht", "auf", "den", "Keks"], "idiom", "annoys me"),
    ("Sie hat Schwein gehabt", ["hat", "Schwein", "gehabt"], "idiom", "was lucky"),

    # Reflexive verbs
    ("Ich freue mich auf das Wochenende", ["freue", "mich", "auf"], "reflexive", "look forward to"),
    ("Er erinnert sich an den Tag", ["erinnert", "sich", "an"], "reflexive", "remembers"),

    # Collocations
    ("Er trifft eine Entscheidung", ["trifft", "Entscheidung"], "collocation", "make a decision"),
    ("Sie macht einen Spaziergang", ["macht", "Spaziergang"], "collocation", "take a walk"),
    ("Ich halte eine Rede", ["halte", "Rede"], "collocation", "give a speech"),
]

# Danish test cases
DANISH_EXAMPLES = [
    # Particle verbs (Partikelverber)
    ("Han kom op med en god idé", ["kom", "op"], "particle_verb", "come up with"),
    ("Hun giver aldrig op", ["giver", "op"], "particle_verb", "give up"),
    ("Jeg ringer dig op i morgen", ["ringer", "op"], "particle_verb", "call"),
    ("Han tager jakken på", ["tager", "på"], "particle_verb", "put on"),
    ("Hun går ud med hunden", ["går", "ud"], "particle_verb", "go out"),
    ("Vi finder ud af det", ["finder", "ud", "af"], "particle_verb", "figure out"),
    ("De kommer tilbage i morgen", ["kommer", "tilbage"], "particle_verb", "come back"),
    ("Han slår op med hende", ["slår", "op"], "particle_verb", "break up"),
    ("Jeg ser frem til ferien", ["ser", "frem", "til"], "particle_verb", "look forward to"),
    ("Hun passer på børnene", ["passer", "på"], "particle_verb", "take care of"),

    # Idioms
    ("Det regner skomagerdrenge", ["regner", "skomagerdrenge"], "idiom", "raining heavily"),
    ("Han har en skrue løs", ["har", "skrue", "løs"], "idiom", "has a screw loose"),
    ("Det er ikke raketvidenskab", ["er", "ikke", "raketvidenskab"], "idiom", "not rocket science"),
    ("Hun slog hovedet på sømmet", ["slog", "hovedet", "på", "sømmet"], "idiom", "hit the nail on the head"),
    ("Han er gået i hundene", ["er", "gået", "i", "hundene"], "idiom", "gone to the dogs"),

    # Reflexive/phrasal
    ("Jeg glæder mig til festen", ["glæder", "mig", "til"], "reflexive", "look forward to"),
    ("Hun besluttede sig for at rejse", ["besluttede", "sig", "for"], "reflexive", "decided to"),

    # Collocations
    ("Han tager en beslutning", ["tager", "beslutning"], "collocation", "make a decision"),
    ("Hun holder en tale", ["holder", "tale"], "collocation", "give a speech"),
    ("Vi går en tur", ["går", "tur"], "collocation", "take a walk"),
]


def get_client():
    if not MICROSOFT_KEY:
        raise ValueError("MICROSOFT_TRANSLATE_API_KEY not set")
    credential = AzureKeyCredential(MICROSOFT_KEY)
    return TextTranslationClient(credential=credential)


def translate_with_alignment(client, text, from_lang, to_lang):
    response = client.translate(
        body=[text],
        to_language=[to_lang],
        from_language=from_lang,
        include_alignment=True,
    )
    result = response[0]
    trans = result.translations[0]
    return {
        "translation": trans.text,
        "alignment": trans.alignment.proj if trans.alignment else "",
    }


def parse_alignment(alignment_str, source, target):
    """Parse alignment and return list of (src_word, tgt_word, src_range, tgt_range)"""
    if not alignment_str:
        return []

    mappings = []
    for mapping in alignment_str.split():
        try:
            src, tgt = mapping.split("-")
            src_start, src_end = map(int, src.split(":"))
            tgt_start, tgt_end = map(int, tgt.split(":"))
            src_word = source[src_start:src_end+1]
            tgt_word = target[tgt_start:tgt_end+1]
            mappings.append({
                "src_word": src_word,
                "tgt_word": tgt_word,
                "src_range": (src_start, src_end),
                "tgt_range": (tgt_start, tgt_end),
            })
        except (ValueError, IndexError):
            continue
    return mappings


def find_word_mappings(mappings, word):
    """Find all mappings for a given source word"""
    return [m for m in mappings if m["src_word"].lower() == word.lower()]


def detect_mwe_signal(mappings, mwe_words, source):
    """
    Detect if alignment shows MWE signal.

    MWE signals:
    1. One source word maps to multiple target words
    2. Multiple source words map to same target word(s)
    3. Source words map to overlapping target ranges
    """
    signals = []

    # Find mappings for each MWE word
    mwe_mappings = {}
    for word in mwe_words:
        word_maps = find_word_mappings(mappings, word)
        if word_maps:
            mwe_mappings[word] = word_maps

    # Check signal 1: one source word → multiple target words
    for word, maps in mwe_mappings.items():
        if len(maps) > 1:
            tgt_words = [m["tgt_word"] for m in maps]
            signals.append(f"'{word}' → multiple: {tgt_words}")

    # Check signal 2: multiple source words → same/overlapping target
    all_tgt_ranges = []
    for word, maps in mwe_mappings.items():
        for m in maps:
            all_tgt_ranges.append((word, m["tgt_range"], m["tgt_word"]))

    # Check for overlapping target ranges
    for i, (w1, r1, t1) in enumerate(all_tgt_ranges):
        for w2, r2, t2 in all_tgt_ranges[i+1:]:
            if w1 != w2:  # Different source words
                # Check overlap
                if r1[0] <= r2[1] and r2[0] <= r1[1]:
                    signals.append(f"'{w1}'+'{w2}' → overlapping target")
                # Check adjacency (within 2 chars)
                elif abs(r1[1] - r2[0]) <= 2 or abs(r2[1] - r1[0]) <= 2:
                    signals.append(f"'{w1}'+'{w2}' → adjacent target: '{t1}'/'{t2}'")

    return signals


def evaluate_example(client, sentence, mwe_words, mwe_type, expected, lang):
    """Evaluate a single example"""
    to_lang = "en" if lang in ["de", "da"] else "da"

    result = translate_with_alignment(client, sentence, lang, to_lang)
    mappings = parse_alignment(result["alignment"], sentence, result["translation"])
    signals = detect_mwe_signal(mappings, mwe_words, sentence)

    return {
        "sentence": sentence,
        "translation": result["translation"],
        "alignment": result["alignment"],
        "mwe_words": mwe_words,
        "mwe_type": mwe_type,
        "expected": expected,
        "signals": signals,
        "detected": len(signals) > 0,
        "mappings": mappings,
    }


def print_result(r, verbose=False):
    """Print a single result"""
    status = "✓" if r["detected"] else "✗"
    print(f"\n{status} [{r['mwe_type']}] {r['expected']}")
    print(f"  Source: \"{r['sentence']}\"")
    print(f"  Target: \"{r['translation']}\"")
    print(f"  MWE words: {r['mwe_words']}")

    if r["signals"]:
        print(f"  Signals: {r['signals']}")
    else:
        print(f"  Signals: NONE DETECTED")

    if verbose:
        print(f"  Alignment: {r['alignment']}")
        print("  Mappings:")
        for m in r["mappings"]:
            print(f"    \"{m['src_word']}\" → \"{m['tgt_word']}\"")


def run_evaluation():
    print("=" * 80)
    print("ALIGNMENT-BASED MWE DETECTION EVALUATION")
    print("=" * 80)

    client = get_client()

    results = {"de": [], "da": []}

    # German examples
    print("\n" + "=" * 80)
    print("GERMAN EXAMPLES (20)")
    print("=" * 80)

    for sentence, mwe_words, mwe_type, expected in GERMAN_EXAMPLES:
        r = evaluate_example(client, sentence, mwe_words, mwe_type, expected, "de")
        results["de"].append(r)
        print_result(r)

    # Danish examples
    print("\n" + "=" * 80)
    print("DANISH EXAMPLES (20)")
    print("=" * 80)

    for sentence, mwe_words, mwe_type, expected in DANISH_EXAMPLES:
        r = evaluate_example(client, sentence, mwe_words, mwe_type, expected, "da")
        results["da"].append(r)
        print_result(r)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for lang, lang_name in [("de", "German"), ("da", "Danish")]:
        lang_results = results[lang]
        detected = sum(1 for r in lang_results if r["detected"])
        total = len(lang_results)

        print(f"\n{lang_name}: {detected}/{total} ({100*detected/total:.0f}%)")

        # By type
        by_type = {}
        for r in lang_results:
            t = r["mwe_type"]
            if t not in by_type:
                by_type[t] = {"detected": 0, "total": 0}
            by_type[t]["total"] += 1
            if r["detected"]:
                by_type[t]["detected"] += 1

        for t, stats in by_type.items():
            pct = 100 * stats["detected"] / stats["total"]
            status = "✓" if pct >= 50 else "✗"
            print(f"  {status} {t}: {stats['detected']}/{stats['total']} ({pct:.0f}%)")

    # Failed cases
    print("\n" + "=" * 80)
    print("FAILED CASES (no MWE signal detected)")
    print("=" * 80)

    for lang in ["de", "da"]:
        failed = [r for r in results[lang] if not r["detected"]]
        if failed:
            print(f"\n{lang.upper()}:")
            for r in failed:
                print(f"  - [{r['mwe_type']}] \"{r['sentence']}\"")
                print(f"    MWE: {r['mwe_words']} → \"{r['translation']}\"")

    return results


if __name__ == "__main__":
    run_evaluation()
