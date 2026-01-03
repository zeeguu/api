"""
Evaluation of alignment for GRAMMATICAL CONSTRUCTIONS:
- Future tense (auxiliary + verb)
- Perfect/past tense (auxiliary + participle)
- Negation markers
- Modal verbs

These are cases where clicking ONE word should include the grammatical marker.

Run with:
  source ~/.venvs/z_env/bin/activate && \
  MICROSOFT_TRANSLATE_API_KEY="..." python -m tools._alignment_evaluation_grammar
"""

import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text import TextTranslationClient

MICROSOFT_KEY = os.environ.get("MICROSOFT_TRANSLATE_API_KEY")

# Format: (sentence, grammatical_unit_words, construction_type, base_verb_meaning, full_meaning)

GERMAN_GRAMMAR = [
    # Future tense (werden + infinitive)
    ("Er wird morgen kommen", ["wird", "kommen"], "future", "comes", "will come"),
    ("Sie wird das Buch lesen", ["wird", "lesen"], "future", "reads", "will read"),
    ("Wir werden nach Hause gehen", ["werden", "gehen"], "future", "go", "will go"),

    # Perfect tense (haben/sein + past participle)
    ("Er hat das Buch gelesen", ["hat", "gelesen"], "perfect", "read (present)", "has read"),
    ("Sie ist nach Hause gegangen", ["ist", "gegangen"], "perfect", "goes", "has gone"),
    ("Wir haben gut geschlafen", ["haben", "geschlafen"], "perfect", "sleep", "have slept"),

    # Negation
    ("Er geht nicht zur Schule", ["geht", "nicht"], "negation", "goes", "doesn't go"),
    ("Sie weiß es nicht", ["weiß", "nicht"], "negation", "knows", "doesn't know"),
    ("Ich verstehe das nicht", ["verstehe", "nicht"], "negation", "understand", "don't understand"),

    # Modal verbs
    ("Er kann gut schwimmen", ["kann", "schwimmen"], "modal", "swims", "can swim"),
    ("Sie muss heute arbeiten", ["muss", "arbeiten"], "modal", "works", "must work"),
    ("Wir wollen ins Kino gehen", ["wollen", "gehen"], "modal", "go", "want to go"),
]

DANISH_GRAMMAR = [
    # Future tense (vil/skal + infinitive)
    ("Han vil rejse i morgen", ["vil", "rejse"], "future", "travels", "will travel"),
    ("Hun skal læse bogen", ["skal", "læse"], "future", "reads", "will read"),
    ("Vi vil gå hjem", ["vil", "gå"], "future", "go/walk", "will go"),

    # Perfect tense (har/er + past participle)
    ("Han har læst bogen", ["har", "læst"], "perfect", "reads", "has read"),
    ("Hun er gået hjem", ["er", "gået"], "perfect", "goes", "has gone"),
    ("Vi har sovet godt", ["har", "sovet"], "perfect", "sleep", "have slept"),

    # Negation
    ("Han går ikke i skole", ["går", "ikke"], "negation", "goes", "doesn't go"),
    ("Hun ved det ikke", ["ved", "ikke"], "negation", "knows", "doesn't know"),
    ("Jeg forstår det ikke", ["forstår", "ikke"], "negation", "understand", "don't understand"),

    # Modal verbs
    ("Han kan svømme godt", ["kan", "svømme"], "modal", "swims", "can swim"),
    ("Hun må arbejde i dag", ["må", "arbejde"], "modal", "works", "must work"),
    ("Vi vil gerne spise", ["vil", "spise"], "modal", "eat", "want to eat"),
]

FRENCH_GRAMMAR = [
    # Future proche (aller + infinitive)
    ("Il va partir demain", ["va", "partir"], "future", "leaves", "is going to leave"),
    ("Elle va lire le livre", ["va", "lire"], "future", "reads", "is going to read"),
    ("Nous allons manger", ["allons", "manger"], "future", "eat", "are going to eat"),

    # Passé composé (avoir/être + past participle)
    ("Il a mangé le gâteau", ["a", "mangé"], "perfect", "eats", "has eaten"),
    ("Elle est partie hier", ["est", "partie"], "perfect", "leaves", "left/has left"),
    ("Nous avons dormi", ["avons", "dormi"], "perfect", "sleep", "have slept"),

    # Negation (ne...pas)
    ("Il ne sait pas", ["ne", "sait", "pas"], "negation", "knows", "doesn't know"),
    ("Elle ne comprend pas", ["ne", "comprend", "pas"], "negation", "understands", "doesn't understand"),
    ("Je ne veux pas partir", ["ne", "veux", "pas"], "negation", "want", "don't want"),

    # Modal verbs
    ("Il peut nager", ["peut", "nager"], "modal", "swims", "can swim"),
    ("Elle doit travailler", ["doit", "travailler"], "modal", "works", "must work"),
    ("Nous voulons manger", ["voulons", "manger"], "modal", "eat", "want to eat"),
]

GREEK_GRAMMAR = [
    # Future (θα + verb)
    ("Θα φύγει αύριο", ["Θα", "φύγει"], "future", "leaves/goes", "will leave"),
    ("Θα διαβάσει το βιβλίο", ["Θα", "διαβάσει"], "future", "reads", "will read"),
    ("Θα πάμε σπίτι", ["Θα", "πάμε"], "future", "go", "will go"),

    # Perfect (έχω + past participle)
    ("Έχει φύγει", ["Έχει", "φύγει"], "perfect", "leaves", "has left"),
    ("Έχει διαβάσει το βιβλίο", ["Έχει", "διαβάσει"], "perfect", "reads", "has read"),
    ("Έχουμε φάει", ["Έχουμε", "φάει"], "perfect", "eat", "have eaten"),

    # Negation (δεν + verb)
    ("Δεν ξέρει", ["Δεν", "ξέρει"], "negation", "knows", "doesn't know"),
    ("Δεν καταλαβαίνω", ["Δεν", "καταλαβαίνω"], "negation", "understand", "don't understand"),
    ("Δεν θέλω", ["Δεν", "θέλω"], "negation", "want", "don't want"),

    # Modal-like constructions
    ("Μπορεί να κολυμπήσει", ["Μπορεί", "να", "κολυμπήσει"], "modal", "swims", "can swim"),
    ("Πρέπει να δουλέψει", ["Πρέπει", "να", "δουλέψει"], "modal", "works", "must work"),
    ("Θέλω να φάω", ["Θέλω", "να", "φάω"], "modal", "eat", "want to eat"),
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


def analyze_grammatical_alignment(mappings, grammar_words, source, target):
    """
    For grammatical constructions, check if:
    1. The words are linked via shared target ranges
    2. One word maps to the grammatical marker in target (will, has, don't, etc.)
    """
    signals = []

    # Find mappings for each grammatical word
    word_to_mappings = {}
    for word in grammar_words:
        word_maps = [m for m in mappings if m["src_word"].lower() == word.lower()]
        if word_maps:
            word_to_mappings[word] = word_maps

    # Check for multi-word mappings
    for word, maps in word_to_mappings.items():
        if len(maps) > 1:
            tgt_words = [m["tgt_word"] for m in maps]
            signals.append(f"'{word}' → {tgt_words}")

    # Check for shared/adjacent target positions
    all_tgt_ranges = []
    for word, maps in word_to_mappings.items():
        for m in maps:
            all_tgt_ranges.append((word, m["tgt_range"], m["tgt_word"]))

    for i, (w1, r1, t1) in enumerate(all_tgt_ranges):
        for w2, r2, t2 in all_tgt_ranges[i+1:]:
            if w1 != w2:
                # Check adjacency
                if abs(r1[1] - r2[0]) <= 2 or abs(r2[1] - r1[0]) <= 2:
                    signals.append(f"'{w1}'+'{w2}' → '{t1}'/'{t2}'")

    return signals


def evaluate_grammar_example(client, sentence, grammar_words, constr_type, base_meaning, full_meaning, lang):
    to_lang = "en"

    result = translate_with_alignment(client, sentence, lang, to_lang)
    mappings = parse_alignment(result["alignment"], sentence, result["translation"])
    signals = analyze_grammatical_alignment(mappings, grammar_words, sentence, result["translation"])

    # Check if the translation captures the full grammatical meaning
    translation_lower = result["translation"].lower()
    has_full_meaning = any(word in translation_lower for word in full_meaning.lower().split())

    return {
        "sentence": sentence,
        "translation": result["translation"],
        "alignment": result["alignment"],
        "grammar_words": grammar_words,
        "construction": constr_type,
        "base_meaning": base_meaning,
        "full_meaning": full_meaning,
        "signals": signals,
        "detected": len(signals) > 0,
        "correct_translation": has_full_meaning,
        "mappings": mappings,
    }


def print_result(r, show_mappings=False):
    status = "✓" if r["detected"] else "✗"
    trans_ok = "✓" if r["correct_translation"] else "?"

    print(f"\n{status} [{r['construction']}] {r['grammar_words']} = \"{r['full_meaning']}\"")
    print(f"  Source: \"{r['sentence']}\"")
    print(f"  Target: \"{r['translation']}\" {trans_ok}")
    print(f"  (clicking just verb would give: \"{r['base_meaning']}\")")

    if r["signals"]:
        print(f"  Signals: {r['signals']}")
    else:
        print(f"  Signals: NONE")

    if show_mappings:
        print(f"  Alignment: {r['alignment']}")
        for m in r["mappings"]:
            print(f"    \"{m['src_word']}\" → \"{m['tgt_word']}\"")


def run_evaluation():
    print("=" * 80)
    print("GRAMMATICAL CONSTRUCTIONS - ALIGNMENT EVALUATION")
    print("=" * 80)
    print("Testing: Future tense, Perfect tense, Negation, Modal verbs")
    print("=" * 80)

    client = get_client()

    all_results = {}

    languages = [
        ("de", "GERMAN", GERMAN_GRAMMAR),
        ("da", "DANISH", DANISH_GRAMMAR),
        ("fr", "FRENCH", FRENCH_GRAMMAR),
        ("el", "GREEK", GREEK_GRAMMAR),
    ]

    for lang_code, lang_name, examples in languages:
        print(f"\n{'=' * 80}")
        print(f"{lang_name} ({len(examples)} examples)")
        print("=" * 80)

        results = []
        for sentence, grammar_words, constr_type, base_meaning, full_meaning in examples:
            r = evaluate_grammar_example(
                client, sentence, grammar_words, constr_type,
                base_meaning, full_meaning, lang_code
            )
            results.append(r)
            print_result(r)

        all_results[lang_code] = results

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for lang_code, lang_name, _ in languages:
        results = all_results[lang_code]
        detected = sum(1 for r in results if r["detected"])
        total = len(results)

        print(f"\n{lang_name}: {detected}/{total} ({100*detected/total:.0f}%)")

        # By construction type
        by_type = {}
        for r in results:
            t = r["construction"]
            if t not in by_type:
                by_type[t] = {"detected": 0, "total": 0}
            by_type[t]["total"] += 1
            if r["detected"]:
                by_type[t]["detected"] += 1

        for t in ["future", "perfect", "negation", "modal"]:
            if t in by_type:
                stats = by_type[t]
                pct = 100 * stats["detected"] / stats["total"]
                status = "✓" if pct >= 50 else "✗"
                print(f"  {status} {t}: {stats['detected']}/{stats['total']} ({pct:.0f}%)")

    # Overall by construction type
    print("\n" + "-" * 40)
    print("OVERALL BY CONSTRUCTION TYPE")
    print("-" * 40)

    overall = {"future": {"d": 0, "t": 0}, "perfect": {"d": 0, "t": 0},
               "negation": {"d": 0, "t": 0}, "modal": {"d": 0, "t": 0}}

    for lang_results in all_results.values():
        for r in lang_results:
            overall[r["construction"]]["t"] += 1
            if r["detected"]:
                overall[r["construction"]]["d"] += 1

    for constr, stats in overall.items():
        pct = 100 * stats["d"] / stats["t"] if stats["t"] > 0 else 0
        status = "✓" if pct >= 50 else "✗"
        print(f"  {status} {constr}: {stats['d']}/{stats['t']} ({pct:.0f}%)")

    # Failed cases
    print("\n" + "=" * 80)
    print("FAILED CASES")
    print("=" * 80)

    for lang_code, lang_name, _ in languages:
        failed = [r for r in all_results[lang_code] if not r["detected"]]
        if failed:
            print(f"\n{lang_name}:")
            for r in failed:
                print(f"  - [{r['construction']}] \"{r['sentence']}\"")
                print(f"    {r['grammar_words']} → \"{r['translation']}\"")


if __name__ == "__main__":
    run_evaluation()
