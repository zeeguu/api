"""
Full MWE Detection Comparison: Alignment vs Stanza

Shows ALL examples with results from both methods.

Run with:
  source ~/.venvs/z_env/bin/activate && \
  MICROSOFT_TRANSLATE_API_KEY="..." python -m tools._mwe_full_comparison
"""

import os
import json
import time
from collections import defaultdict
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text import TextTranslationClient

MICROSOFT_KEY = os.environ.get("MICROSOFT_TRANSLATE_API_KEY")

# =============================================================================
# TEST DATA - ALL EXAMPLES
# =============================================================================

ALL_EXAMPLES = [
    # ==== GERMAN ====
    # Particle verbs (separable)
    ("Ich rufe dich morgen an", ["rufe", "an"], "particle_verb", "de", "call"),
    ("Er steht jeden Tag früh auf", ["steht", "auf"], "particle_verb", "de", "gets up"),
    ("Sie gibt niemals auf", ["gibt", "auf"], "particle_verb", "de", "gives up"),
    ("Wir fangen morgen an", ["fangen", "an"], "particle_verb", "de", "start"),
    ("Er kommt heute Abend zurück", ["kommt", "zurück"], "particle_verb", "de", "comes back"),
    ("Sie bringt ihre Freundin mit", ["bringt", "mit"], "particle_verb", "de", "brings along"),
    ("Ich schaue mir den Film an", ["schaue", "an"], "particle_verb", "de", "watch"),
    ("Er macht das Licht aus", ["macht", "aus"], "particle_verb", "de", "turns off"),
    ("Sie zieht sich warm an", ["zieht", "an"], "particle_verb", "de", "dresses"),
    ("Wir laden alle Freunde ein", ["laden", "ein"], "particle_verb", "de", "invite"),

    # German idioms
    ("Das ist mir Wurst", ["ist", "mir", "Wurst"], "idiom", "de", "I don't care"),
    ("Er hat einen Vogel", ["hat", "einen", "Vogel"], "idiom", "de", "he's crazy"),
    ("Ich drücke dir die Daumen", ["drücke", "die", "Daumen"], "idiom", "de", "fingers crossed"),

    # German grammatical
    ("Er wird morgen kommen", ["wird", "kommen"], "future", "de", "will come"),
    ("Er hat das Buch gelesen", ["hat", "gelesen"], "perfect", "de", "has read"),
    ("Sie ist nach Hause gegangen", ["ist", "gegangen"], "perfect", "de", "has gone"),
    ("Er geht nicht zur Schule", ["geht", "nicht"], "negation", "de", "doesn't go"),
    ("Er kann gut schwimmen", ["kann", "schwimmen"], "modal", "de", "can swim"),

    # ==== DANISH ====
    # Particle verbs
    ("Han kom op med en god idé", ["kom", "op"], "particle_verb", "da", "came up with"),
    ("Hun giver aldrig op", ["giver", "op"], "particle_verb", "da", "gives up"),
    ("Jeg ringer dig op i morgen", ["ringer", "op"], "particle_verb", "da", "call"),
    ("Han tager jakken på", ["tager", "på"], "particle_verb", "da", "puts on"),
    ("Hun går ud med hunden", ["går", "ud"], "particle_verb", "da", "goes out"),
    ("Vi finder ud af det", ["finder", "ud"], "particle_verb", "da", "figure out"),
    ("De kommer tilbage i morgen", ["kommer", "tilbage"], "particle_verb", "da", "come back"),
    ("Han slår op med hende", ["slår", "op"], "particle_verb", "da", "breaks up"),
    ("Jeg ser frem til ferien", ["ser", "frem"], "particle_verb", "da", "look forward"),
    ("Hun passer på børnene", ["passer", "på"], "particle_verb", "da", "takes care"),

    # Danish idioms
    ("Han har en skrue løs", ["har", "skrue", "løs"], "idiom", "da", "has a screw loose"),
    ("Hun slog hovedet på sømmet", ["slog", "hovedet", "sømmet"], "idiom", "da", "hit the nail"),

    # Danish grammatical
    ("Han vil rejse i morgen", ["vil", "rejse"], "future", "da", "will travel"),
    ("Han har læst bogen", ["har", "læst"], "perfect", "da", "has read"),
    ("Han går ikke i skole", ["går", "ikke"], "negation", "da", "doesn't go"),
    ("Han kan svømme godt", ["kan", "svømme"], "modal", "da", "can swim"),

    # ==== FRENCH ====
    # Phrasal expressions
    ("Il a mis le projet sur pied", ["mis", "sur", "pied"], "particle_verb", "fr", "set up"),
    ("Elle se rend compte de son erreur", ["rend", "compte"], "particle_verb", "fr", "realizes"),

    # French idioms
    ("Il pleut des cordes", ["pleut", "cordes"], "idiom", "fr", "raining heavily"),
    ("Elle a le cafard", ["a", "cafard"], "idiom", "fr", "feeling down"),

    # French grammatical
    ("Il va partir demain", ["va", "partir"], "future", "fr", "going to leave"),
    ("Il a mangé le gâteau", ["a", "mangé"], "perfect", "fr", "has eaten"),
    ("Il ne sait pas", ["ne", "sait", "pas"], "negation", "fr", "doesn't know"),
    ("Il peut nager", ["peut", "nager"], "modal", "fr", "can swim"),

    # ==== GREEK ====
    # Greek grammatical (the user's specific examples)
    ("Θα φύγει αύριο", ["Θα", "φύγει"], "future", "el", "will leave"),
    ("Θα διαβάσει το βιβλίο", ["Θα", "διαβάσει"], "future", "el", "will read"),
    ("Θα πάμε σπίτι", ["Θα", "πάμε"], "future", "el", "will go"),
    ("Δεν ξέρει", ["Δεν", "ξέρει"], "negation", "el", "doesn't know"),
    ("Δεν καταλαβαίνω", ["Δεν", "καταλαβαίνω"], "negation", "el", "don't understand"),
    ("Δεν θέλω", ["Δεν", "θέλω"], "negation", "el", "don't want"),
    ("Έχει φύγει", ["Έχει", "φύγει"], "perfect", "el", "has left"),
    ("Έχει διαβάσει το βιβλίο", ["Έχει", "διαβάσει"], "perfect", "el", "has read"),
    ("Μπορεί να κολυμπήσει", ["Μπορεί", "κολυμπήσει"], "modal", "el", "can swim"),
    ("Θέλω να φάω", ["Θέλω", "φάω"], "modal", "el", "want to eat"),

    # ==== SPANISH ====
    # Phrasal verbs
    ("Llevó a cabo el plan", ["Llevó", "a", "cabo"], "particle_verb", "es", "carried out"),
    ("Dio a luz a un niño", ["Dio", "a", "luz"], "particle_verb", "es", "gave birth"),

    # Spanish grammatical
    ("Va a comer", ["Va", "a", "comer"], "future", "es", "going to eat"),
    ("Ha comido", ["Ha", "comido"], "perfect", "es", "has eaten"),
    ("No sabe", ["No", "sabe"], "negation", "es", "doesn't know"),
    ("Puede nadar", ["Puede", "nadar"], "modal", "es", "can swim"),

    # ==== SWEDISH ====
    # Particle verbs
    ("Hon ger aldrig upp", ["ger", "upp"], "particle_verb", "sv", "gives up"),
    ("Han kommer tillbaka", ["kommer", "tillbaka"], "particle_verb", "sv", "comes back"),

    # Swedish grammatical
    ("Han ska resa", ["ska", "resa"], "future", "sv", "will travel"),
    ("Han har läst", ["har", "läst"], "perfect", "sv", "has read"),
    ("Han går inte", ["går", "inte"], "negation", "sv", "doesn't go"),
    ("Han kan simma", ["kan", "simma"], "modal", "sv", "can swim"),

    # ==== DUTCH ====
    # Particle verbs
    ("Ik bel je morgen op", ["bel", "op"], "particle_verb", "nl", "call"),
    ("Hij geeft nooit op", ["geeft", "op"], "particle_verb", "nl", "gives up"),

    # Dutch grammatical
    ("Hij zal komen", ["zal", "komen"], "future", "nl", "will come"),
    ("Hij heeft gelezen", ["heeft", "gelezen"], "perfect", "nl", "has read"),
    ("Hij gaat niet", ["gaat", "niet"], "negation", "nl", "doesn't go"),
    ("Hij kan zwemmen", ["kan", "zwemmen"], "modal", "nl", "can swim"),
]


class SimpleToken:
    """Token class for MWE detector"""
    def __init__(self, text, dep, head, lemma):
        self.text = text
        self.dep = dep
        self.head = head
        self.lemma = lemma


# Stanza pipelines cache
_stanza_pipelines = {}


def get_stanza_pipeline(lang):
    """Get or create Stanza pipeline"""
    if lang not in _stanza_pipelines:
        import stanza
        print(f"  Loading Stanza model for {lang}...")
        _stanza_pipelines[lang] = stanza.Pipeline(
            lang=lang,
            processors='tokenize,pos,lemma,depparse',
            verbose=False
        )
    return _stanza_pipelines[lang]


def detect_with_stanza(sentence, mwe_words, lang):
    """Detect particle verb using Stanza dependency parsing"""
    # Only supported languages
    if lang not in ["de", "da", "nl", "sv", "fr", "es", "el"]:
        return {"detected": False, "mwes": [], "reason": "language not supported"}

    from zeeguu.core.language.mwe_detector import detect_particle_verbs

    try:
        nlp = get_stanza_pipeline(lang)
        doc = nlp(sentence)

        # Convert to tokens
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

        # Check if we found the expected MWE
        detected = False
        for mwe in mwes:
            mwe_texts = [tokens[i].text.lower() for i in mwe['all_positions']]
            # Check if any of the expected words are in the MWE
            matches = sum(1 for w in mwe_words if w.lower() in mwe_texts)
            if matches >= 2:  # At least 2 words match
                detected = True
                break

        return {
            "detected": detected,
            "mwes": mwes,
            "tokens": [(t.text, t.dep) for t in tokens],
        }
    except Exception as e:
        return {"detected": False, "mwes": [], "error": str(e)}


def get_client():
    if not MICROSOFT_KEY:
        raise ValueError("MICROSOFT_TRANSLATE_API_KEY not set")
    credential = AzureKeyCredential(MICROSOFT_KEY)
    return TextTranslationClient(credential=credential)


def analyze_alignment(sentence, mwe_words, translation, alignment_str):
    """Analyze alignment for MWE signals"""
    if not alignment_str:
        return {"detected": False, "signals": [], "word_mappings": {}, "missing_words": mwe_words}

    # Parse alignment
    mappings = []
    for m in alignment_str.split():
        try:
            src, tgt = m.split("-")
            src_start, src_end = map(int, src.split(":"))
            tgt_start, tgt_end = map(int, tgt.split(":"))
            src_word = sentence[src_start:src_end+1]
            tgt_word = translation[tgt_start:tgt_end+1]
            mappings.append({
                "src": src_word, "tgt": tgt_word,
                "src_range": (src_start, src_end),
                "tgt_range": (tgt_start, tgt_end),
            })
        except:
            continue

    # Find mappings for MWE words
    word_mappings = {}
    missing_words = []
    for word in mwe_words:
        word_maps = [m for m in mappings if m["src"].lower() == word.lower()]
        if word_maps:
            word_mappings[word] = [m["tgt"] for m in word_maps]
        else:
            missing_words.append(word)

    # Detect signals
    signals = []

    # Signal 1: One word maps to multiple targets
    for word, tgts in word_mappings.items():
        if len(tgts) > 1:
            signals.append(f"multi:{word}→{tgts}")

    # Signal 2: Adjacent/overlapping targets
    mwe_maps = [m for m in mappings if m["src"].lower() in [w.lower() for w in mwe_words]]
    for i, m1 in enumerate(mwe_maps):
        for m2 in mwe_maps[i+1:]:
            if m1["src"].lower() != m2["src"].lower():
                gap = min(abs(m1["tgt_range"][1] - m2["tgt_range"][0]),
                         abs(m2["tgt_range"][1] - m1["tgt_range"][0]))
                if gap <= 2:
                    signals.append(f"adjacent:{m1['src']}+{m2['src']}")

    return {
        "detected": len(signals) > 0,
        "signals": signals,
        "word_mappings": word_mappings,
        "missing_words": missing_words,
        "all_mappings": mappings,
    }


def evaluate_example(client, sentence, mwe_words, constr_type, lang, expected, use_stanza=False):
    """Evaluate a single example with both methods"""
    # Microsoft alignment
    response = client.translate(
        body=[sentence],
        to_language=["en"],
        from_language=lang,
        include_alignment=True,
    )

    result = response[0].translations[0]
    translation = result.text
    alignment = result.alignment.proj if result.alignment else ""

    align_analysis = analyze_alignment(sentence, mwe_words, translation, alignment)

    # Stanza (only for particle verbs and supported languages)
    stanza_result = None
    if use_stanza and constr_type == "particle_verb":
        stanza_result = detect_with_stanza(sentence, mwe_words, lang)

    return {
        "sentence": sentence,
        "mwe_words": mwe_words,
        "construction": constr_type,
        "lang": lang,
        "expected": expected,
        "translation": translation,
        "alignment": alignment,
        "align_detected": align_analysis["detected"],
        "align_signals": align_analysis["signals"],
        "align_mappings": align_analysis["word_mappings"],
        "align_missing": align_analysis["missing_words"],
        "all_mappings": align_analysis["all_mappings"],
        "stanza_result": stanza_result,
        "stanza_detected": stanza_result["detected"] if stanza_result else None,
    }


def print_example(r, idx):
    """Print a single example with full details"""
    align_icon = "✓" if r["align_detected"] else "✗"

    # Stanza icon
    if r["stanza_detected"] is None:
        stanza_icon = "-"
    elif r["stanza_detected"]:
        stanza_icon = "✓"
    else:
        stanza_icon = "✗"

    # Combined result
    combined = r["align_detected"] or (r["stanza_detected"] if r["stanza_detected"] is not None else False)
    combined_icon = "✓" if combined else "✗"

    print(f"\n{idx:2}. [{r['lang'].upper()}] [{r['construction']}]")
    print(f"    Source:   \"{r['sentence']}\"")
    print(f"    MWE:      {r['mwe_words']} → \"{r['expected']}\"")
    print(f"    Target:   \"{r['translation']}\"")
    print(f"    ")
    print(f"    Alignment: {align_icon}", end="")
    if r["align_signals"]:
        print(f"  {r['align_signals']}")
    elif r["align_missing"]:
        print(f"  (missing: {r['align_missing']})")
    else:
        print(f"  (no signal)")

    # Show word mappings
    if r["align_mappings"]:
        mappings_str = ", ".join(f"{k}→{v}" for k, v in r["align_mappings"].items())
        print(f"               Mappings: {mappings_str}")

    # Stanza result (only for particle verbs)
    if r["construction"] == "particle_verb":
        print(f"    Stanza:    {stanza_icon}", end="")
        if r["stanza_result"]:
            if r["stanza_result"].get("mwes"):
                print(f"  Found compound:prt")
            elif r["stanza_result"].get("error"):
                print(f"  Error: {r['stanza_result']['error']}")
            else:
                # Show what dependencies were found
                deps = [t for t in r["stanza_result"].get("tokens", []) if t[1] == "compound:prt"]
                if deps:
                    print(f"  compound:prt found but not matching")
                else:
                    print(f"  No compound:prt found")
        else:
            print(f"  N/A")
        print(f"    Combined:  {combined_icon}")


def main():
    print("=" * 80)
    print("MWE DETECTION: FULL COMPARISON - ALIGNMENT vs STANZA")
    print("=" * 80)

    print("\nLoading Microsoft Translator...")
    client = get_client()

    print("Pre-loading Stanza models for particle verb languages...")
    for lang in ["de", "da", "nl", "sv"]:
        try:
            get_stanza_pipeline(lang)
        except Exception as e:
            print(f"  Warning: Could not load {lang}: {e}")

    print(f"\nEvaluating {len(ALL_EXAMPLES)} examples...\n")

    results = []
    current_lang = None

    for i, (sentence, mwe_words, constr_type, lang, expected) in enumerate(ALL_EXAMPLES):
        # Print language header
        if lang != current_lang:
            current_lang = lang
            print(f"\n{'=' * 80}")
            print(f"  {lang.upper()}")
            print(f"{'=' * 80}")

        r = evaluate_example(client, sentence, mwe_words, constr_type, lang, expected, use_stanza=True)
        results.append(r)
        print_example(r, i + 1)

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    # Overall stats
    align_detected = sum(1 for r in results if r["align_detected"])
    particle_results = [r for r in results if r["construction"] == "particle_verb"]
    stanza_detected = sum(1 for r in particle_results if r["stanza_detected"])
    combined_detected = sum(1 for r in particle_results
                          if r["align_detected"] or (r["stanza_detected"] or False))

    print(f"\nOverall Alignment Detection: {align_detected}/{len(results)} ({100*align_detected/len(results):.0f}%)")
    print(f"\nParticle Verbs Only ({len(particle_results)} examples):")
    print(f"  Alignment: {sum(1 for r in particle_results if r['align_detected'])}/{len(particle_results)}")
    print(f"  Stanza:    {stanza_detected}/{len(particle_results)}")
    print(f"  Combined:  {combined_detected}/{len(particle_results)}")

    # By language
    print("\n" + "-" * 60)
    print("BY LANGUAGE")
    print("-" * 60)

    lang_stats = defaultdict(lambda: {"align": 0, "stanza": 0, "combined": 0, "total": 0, "pv_total": 0})

    for r in results:
        lang_stats[r["lang"]]["total"] += 1
        if r["align_detected"]:
            lang_stats[r["lang"]]["align"] += 1
        if r["construction"] == "particle_verb":
            lang_stats[r["lang"]]["pv_total"] += 1
            if r["stanza_detected"]:
                lang_stats[r["lang"]]["stanza"] += 1
            if r["align_detected"] or (r["stanza_detected"] or False):
                lang_stats[r["lang"]]["combined"] += 1

    print(f"\n{'Lang':<6} {'Align':<15} {'Stanza (PV)':<15} {'Combined (PV)':<15}")
    print("-" * 51)
    for lang in ["de", "da", "fr", "el", "es", "sv", "nl"]:
        s = lang_stats[lang]
        align_pct = f"{s['align']}/{s['total']} ({100*s['align']/s['total']:.0f}%)" if s['total'] > 0 else "-"
        if s['pv_total'] > 0:
            stanza_pct = f"{s['stanza']}/{s['pv_total']} ({100*s['stanza']/s['pv_total']:.0f}%)"
            combined_pct = f"{s['combined']}/{s['pv_total']} ({100*s['combined']/s['pv_total']:.0f}%)"
        else:
            stanza_pct = "-"
            combined_pct = "-"
        print(f"{lang:<6} {align_pct:<15} {stanza_pct:<15} {combined_pct:<15}")

    # By construction type
    print("\n" + "-" * 60)
    print("BY CONSTRUCTION TYPE (Alignment)")
    print("-" * 60)

    type_stats = defaultdict(lambda: {"detected": 0, "total": 0})
    for r in results:
        type_stats[r["construction"]]["total"] += 1
        if r["align_detected"]:
            type_stats[r["construction"]]["detected"] += 1

    print(f"\n{'Type':<15} {'Detected':<15} {'Rate':<10}")
    print("-" * 40)
    for ctype in ["particle_verb", "idiom", "future", "perfect", "negation", "modal"]:
        if ctype in type_stats:
            s = type_stats[ctype]
            rate = 100 * s["detected"] / s["total"]
            print(f"{ctype:<15} {s['detected']}/{s['total']:<12} {rate:.0f}%")

    # Particle verb comparison table
    print("\n" + "-" * 60)
    print("PARTICLE VERB COMPARISON: ALIGNMENT vs STANZA")
    print("-" * 60)

    print(f"\n{'Lang':<6} {'Alignment':<12} {'Stanza':<12} {'Combined':<12} {'Improvement':<12}")
    print("-" * 54)

    for lang in ["de", "da", "nl", "sv"]:
        pv_results = [r for r in results if r["construction"] == "particle_verb" and r["lang"] == lang]
        if not pv_results:
            continue

        align_det = sum(1 for r in pv_results if r["align_detected"])
        stanza_det = sum(1 for r in pv_results if r["stanza_detected"])
        combined_det = sum(1 for r in pv_results if r["align_detected"] or (r["stanza_detected"] or False))
        total = len(pv_results)

        align_pct = 100 * align_det / total
        stanza_pct = 100 * stanza_det / total
        combined_pct = 100 * combined_det / total
        improvement = combined_pct - max(align_pct, stanza_pct)

        print(f"{lang:<6} {align_det}/{total} ({align_pct:.0f}%)   {stanza_det}/{total} ({stanza_pct:.0f}%)   {combined_det}/{total} ({combined_pct:.0f}%)   +{improvement:.0f}%")

    # Failed cases
    print("\n" + "-" * 60)
    print("FAILED CASES (Both methods failed)")
    print("-" * 60)

    both_failed = [r for r in results
                   if not r["align_detected"] and
                   (r["stanza_detected"] is None or not r["stanza_detected"])]

    for r in both_failed:
        print(f"\n  [{r['lang'].upper()}] \"{r['sentence']}\"")
        print(f"       MWE: {r['mwe_words']} → \"{r['translation']}\"")
        if r["align_missing"]:
            print(f"       Alignment: missing {r['align_missing']}")
        if r["stanza_result"] and not r["stanza_result"].get("mwes"):
            print(f"       Stanza: no compound:prt found")

    # Save results
    with open("/tmp/mwe_full_comparison.json", "w") as f:
        # Convert for JSON serialization
        json_results = []
        for r in results:
            jr = {k: v for k, v in r.items() if k != "all_mappings"}
            json_results.append(jr)
        json.dump(json_results, f, indent=2, ensure_ascii=False)

    print(f"\n\nResults saved to /tmp/mwe_full_comparison.json")


if __name__ == "__main__":
    main()
