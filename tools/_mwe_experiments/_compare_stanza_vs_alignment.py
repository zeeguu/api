"""
Compare Stanza MWE detection vs Microsoft Alignment for particle verbs.

Question: Would Stanza give us more reliable particle verb detection?

Run with:
  source ~/.venvs/z_env/bin/activate && \
  MICROSOFT_TRANSLATE_API_KEY="..." python -m tools._compare_stanza_vs_alignment
"""

import os
import time
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text import TextTranslationClient

MICROSOFT_KEY = os.environ.get("MICROSOFT_TRANSLATE_API_KEY")

# Particle verb test cases from both languages
# Format: (sentence, verb, particle, lang, expected_translation)
PARTICLE_VERB_EXAMPLES = [
    # German separable verbs
    ("Ich rufe dich morgen an", "rufe", "an", "de", "call"),
    ("Er steht jeden Tag früh auf", "steht", "auf", "de", "gets up"),
    ("Sie gibt niemals auf", "gibt", "auf", "de", "gives up"),
    ("Wir fangen morgen an", "fangen", "an", "de", "start"),
    ("Er kommt heute Abend zurück", "kommt", "zurück", "de", "comes back"),
    ("Sie bringt ihre Freundin mit", "bringt", "mit", "de", "brings"),
    ("Ich schaue mir den Film an", "schaue", "an", "de", "watch"),
    ("Er macht das Licht aus", "macht", "aus", "de", "turns off"),
    ("Sie zieht sich warm an", "zieht", "an", "de", "dresses"),
    ("Wir laden alle Freunde ein", "laden", "ein", "de", "invite"),

    # Danish particle verbs
    ("Han kom op med en god idé", "kom", "op", "da", "came up"),
    ("Hun giver aldrig op", "giver", "op", "da", "gives up"),
    ("Jeg ringer dig op i morgen", "ringer", "op", "da", "call"),
    ("Han tager jakken på", "tager", "på", "da", "puts on"),
    ("Hun går ud med hunden", "går", "ud", "da", "walks/goes out"),
    ("Vi finder ud af det", "finder", "ud", "da", "figure out"),
    ("De kommer tilbage i morgen", "kommer", "tilbage", "da", "come back"),
    ("Han slår op med hende", "slår", "op", "da", "breaks up"),
    ("Jeg ser frem til ferien", "ser", "frem", "da", "look forward"),
    ("Hun passer på børnene", "passer", "på", "da", "takes care"),
]


class SimpleToken:
    """Token class for MWE detector"""
    def __init__(self, text, dep, head, lemma):
        self.text = text
        self.dep = dep
        self.head = head
        self.lemma = lemma


def get_stanza_pipeline(lang):
    """Get or create Stanza pipeline"""
    import stanza
    if not hasattr(get_stanza_pipeline, 'pipelines'):
        get_stanza_pipeline.pipelines = {}
    if lang not in get_stanza_pipeline.pipelines:
        print(f"  Loading Stanza model for {lang}...")
        get_stanza_pipeline.pipelines[lang] = stanza.Pipeline(
            lang=lang,
            processors='tokenize,pos,lemma,depparse',
            verbose=False
        )
    return get_stanza_pipeline.pipelines[lang]


def detect_with_stanza(sentence, verb, particle, lang):
    """Detect particle verb using Stanza dependency parsing"""
    from tools._mwe_experiments.detector import detect_particle_verbs

    nlp = get_stanza_pipeline(lang)

    start = time.perf_counter()
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
    elapsed = (time.perf_counter() - start) * 1000

    # Check if we found the expected particle verb
    detected = False
    for mwe in mwes:
        mwe_texts = [tokens[i].text.lower() for i in mwe['all_positions']]
        if verb.lower() in mwe_texts and particle.lower() in mwe_texts:
            detected = True
            break

    return {
        "detected": detected,
        "mwes": mwes,
        "tokens": [(t.text, t.dep, t.head) for t in tokens],
        "time_ms": elapsed,
    }


def get_ms_client():
    if not MICROSOFT_KEY:
        raise ValueError("MICROSOFT_TRANSLATE_API_KEY not set")
    credential = AzureKeyCredential(MICROSOFT_KEY)
    return TextTranslationClient(credential=credential)


def detect_with_alignment(client, sentence, verb, particle, lang):
    """Detect particle verb using Microsoft alignment"""
    start = time.perf_counter()

    response = client.translate(
        body=[sentence],
        to_language=["en"],
        from_language=lang,
        include_alignment=True,
    )

    elapsed = (time.perf_counter() - start) * 1000

    result = response[0]
    trans = result.translations[0]
    translation = trans.text
    alignment = trans.alignment.proj if trans.alignment else ""

    # Parse alignment
    mappings = []
    for mapping in alignment.split():
        try:
            src, tgt = mapping.split("-")
            src_start, src_end = map(int, src.split(":"))
            tgt_start, tgt_end = map(int, tgt.split(":"))
            src_word = sentence[src_start:src_end+1]
            tgt_word = translation[tgt_start:tgt_end+1]
            mappings.append({
                "src": src_word,
                "tgt": tgt_word,
                "src_range": (src_start, src_end),
                "tgt_range": (tgt_start, tgt_end),
            })
        except (ValueError, IndexError):
            continue

    # Check for MWE signal
    verb_maps = [m for m in mappings if m["src"].lower() == verb.lower()]
    particle_maps = [m for m in mappings if m["src"].lower() == particle.lower()]

    signals = []

    # Signal 1: verb maps to multiple target words
    if len(verb_maps) > 1:
        signals.append(f"verb→multiple: {[m['tgt'] for m in verb_maps]}")

    # Signal 2: particle maps to multiple target words
    if len(particle_maps) > 1:
        signals.append(f"particle→multiple: {[m['tgt'] for m in particle_maps]}")

    # Signal 3: adjacent/overlapping targets
    if verb_maps and particle_maps:
        for vm in verb_maps:
            for pm in particle_maps:
                if abs(vm["tgt_range"][1] - pm["tgt_range"][0]) <= 2 or \
                   abs(pm["tgt_range"][1] - vm["tgt_range"][0]) <= 2:
                    signals.append(f"adjacent: {vm['tgt']}/{pm['tgt']}")

    return {
        "detected": len(signals) > 0,
        "signals": signals,
        "translation": translation,
        "alignment": alignment,
        "time_ms": elapsed,
    }


def run_comparison():
    print("=" * 80)
    print("STANZA vs ALIGNMENT - PARTICLE VERB DETECTION COMPARISON")
    print("=" * 80)

    client = get_ms_client()

    results = []

    print("\nWarming up Stanza models...")
    get_stanza_pipeline("de")
    get_stanza_pipeline("da")
    print("Done.\n")

    for sentence, verb, particle, lang, expected in PARTICLE_VERB_EXAMPLES:
        print(f"\n--- [{lang.upper()}] \"{sentence}\" ---")
        print(f"    Expected: {verb}...{particle} → \"{expected}\"")

        # Stanza detection
        stanza_result = detect_with_stanza(sentence, verb, particle, lang)

        # Alignment detection
        align_result = detect_with_alignment(client, sentence, verb, particle, lang)

        stanza_ok = "✓" if stanza_result["detected"] else "✗"
        align_ok = "✓" if align_result["detected"] else "✗"

        print(f"    Stanza:    {stanza_ok} ({stanza_result['time_ms']:.0f}ms)")
        if stanza_result["mwes"]:
            for mwe in stanza_result["mwes"]:
                print(f"               Found: {mwe['verb_text']}...{mwe['particle_texts']}")
        elif not stanza_result["detected"]:
            # Show why it failed
            deps = [(t[0], t[1]) for t in stanza_result["tokens"] if t[1] == "compound:prt"]
            if deps:
                print(f"               compound:prt found but not matching: {deps}")
            else:
                print(f"               No compound:prt dependency found")

        print(f"    Alignment: {align_ok} ({align_result['time_ms']:.0f}ms) → \"{align_result['translation']}\"")
        if align_result["signals"]:
            print(f"               Signals: {align_result['signals']}")
        else:
            print(f"               No MWE signal in alignment")

        results.append({
            "sentence": sentence,
            "verb": verb,
            "particle": particle,
            "lang": lang,
            "stanza_detected": stanza_result["detected"],
            "align_detected": align_result["detected"],
            "stanza_time": stanza_result["time_ms"],
            "align_time": align_result["time_ms"],
            "translation": align_result["translation"],
        })

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    stanza_detected = sum(1 for r in results if r["stanza_detected"])
    align_detected = sum(1 for r in results if r["align_detected"])
    total = len(results)

    print(f"\nOverall Detection Rate:")
    print(f"  Stanza:    {stanza_detected}/{total} ({100*stanza_detected/total:.0f}%)")
    print(f"  Alignment: {align_detected}/{total} ({100*align_detected/total:.0f}%)")

    # By language
    for lang in ["de", "da"]:
        lang_results = [r for r in results if r["lang"] == lang]
        stanza_lang = sum(1 for r in lang_results if r["stanza_detected"])
        align_lang = sum(1 for r in lang_results if r["align_detected"])
        lang_total = len(lang_results)
        print(f"\n  {lang.upper()}:")
        print(f"    Stanza:    {stanza_lang}/{lang_total} ({100*stanza_lang/lang_total:.0f}%)")
        print(f"    Alignment: {align_lang}/{lang_total} ({100*align_lang/lang_total:.0f}%)")

    # Average timing
    avg_stanza = sum(r["stanza_time"] for r in results) / len(results)
    avg_align = sum(r["align_time"] for r in results) / len(results)
    print(f"\nAverage Time:")
    print(f"  Stanza:    {avg_stanza:.0f}ms (parsing only)")
    print(f"  Alignment: {avg_align:.0f}ms (includes translation)")

    # Cases where they differ
    print("\n" + "-" * 40)
    print("DISAGREEMENTS")
    print("-" * 40)

    stanza_only = [r for r in results if r["stanza_detected"] and not r["align_detected"]]
    align_only = [r for r in results if r["align_detected"] and not r["stanza_detected"]]
    both_fail = [r for r in results if not r["stanza_detected"] and not r["align_detected"]]

    if stanza_only:
        print(f"\nStanza detected, Alignment missed ({len(stanza_only)}):")
        for r in stanza_only:
            print(f"  - \"{r['sentence']}\"")
            print(f"    {r['verb']}...{r['particle']} → \"{r['translation']}\"")

    if align_only:
        print(f"\nAlignment detected, Stanza missed ({len(align_only)}):")
        for r in align_only:
            print(f"  - \"{r['sentence']}\"")
            print(f"    {r['verb']}...{r['particle']} → \"{r['translation']}\"")

    if both_fail:
        print(f"\nBoth failed ({len(both_fail)}):")
        for r in both_fail:
            print(f"  - \"{r['sentence']}\"")
            print(f"    {r['verb']}...{r['particle']} → \"{r['translation']}\"")

    # Recommendation
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if stanza_detected > align_detected:
        diff = stanza_detected - align_detected
        print(f"\nStanza is MORE RELIABLE for particle verbs (+{diff} detections)")
        print("Consider: Stanza for MWE detection, then translate the detected phrase")
    elif align_detected > stanza_detected:
        diff = align_detected - stanza_detected
        print(f"\nAlignment is MORE RELIABLE for particle verbs (+{diff} detections)")
        print("Consider: Use alignment-based detection")
    else:
        print(f"\nBoth approaches have SAME detection rate")
        print("Consider: Alignment is simpler (no extra models)")


if __name__ == "__main__":
    run_comparison()
