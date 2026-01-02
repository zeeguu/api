"""
Generate detailed appendix for MWE report.
Shows full Stanza parse and Microsoft alignment for each example.

Languages: German, Italian, Spanish, French, Romanian, English

Run with:
  MICROSOFT_TRANSLATE_API_KEY="..." /Users/mircea/.venvs/z_env/bin/python -m tools._mwe_appendix_generator
"""

import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text import TextTranslationClient
import stanza

MICROSOFT_KEY = os.environ.get("MICROSOFT_TRANSLATE_API_KEY")

# Examples for each language
# Format: (sentence, mwe_words, construction_type, expected_meaning)

EXAMPLES = {
    "de": [
        # Particle verbs
        ("Ich rufe dich morgen an", ["rufe", "an"], "particle_verb", "call"),
        ("Er steht jeden Tag früh auf", ["steht", "auf"], "particle_verb", "gets up"),
        ("Sie gibt niemals auf", ["gibt", "auf"], "particle_verb", "gives up"),
        ("Er macht das Licht aus", ["macht", "aus"], "particle_verb", "turns off"),
        ("Sie zieht sich warm an", ["zieht", "an"], "particle_verb", "dresses"),
        # Idioms
        ("Das ist mir Wurst", ["ist", "mir", "Wurst"], "idiom", "I don't care"),
        ("Ich drücke dir die Daumen", ["drücke", "die", "Daumen"], "idiom", "fingers crossed"),
        # Grammatical
        ("Er wird morgen kommen", ["wird", "kommen"], "future", "will come"),
        ("Er hat das Buch gelesen", ["hat", "gelesen"], "perfect", "has read"),
        ("Er geht nicht zur Schule", ["geht", "nicht"], "negation", "doesn't go"),
    ],
    "it": [
        # Phrasal verbs / MWEs
        ("Lui ha messo in piedi il progetto", ["messo", "in", "piedi"], "particle_verb", "set up"),
        ("Lei si rende conto del problema", ["rende", "conto"], "particle_verb", "realizes"),
        ("Hanno dato alla luce un bambino", ["dato", "alla", "luce"], "particle_verb", "gave birth"),
        # Idioms
        ("Piove a catinelle", ["Piove", "catinelle"], "idiom", "raining heavily"),
        ("Ho le mani in pasta", ["ho", "mani", "pasta"], "idiom", "involved in"),
        # Grammatical
        ("Lui andrà domani", ["andrà"], "future", "will go"),
        ("Lui ha mangiato la torta", ["ha", "mangiato"], "perfect", "has eaten"),
        ("Non so", ["Non", "so"], "negation", "don't know"),
        ("Lui può nuotare", ["può", "nuotare"], "modal", "can swim"),
    ],
    "es": [
        # Phrasal verbs
        ("Llevó a cabo el plan", ["Llevó", "a", "cabo"], "particle_verb", "carried out"),
        ("Dio a luz a un niño", ["Dio", "a", "luz"], "particle_verb", "gave birth"),
        ("Echó de menos a su amigo", ["Echó", "de", "menos"], "particle_verb", "missed"),
        # Idioms
        ("Está lloviendo a cántaros", ["lloviendo", "cántaros"], "idiom", "raining heavily"),
        ("Meter la pata", ["Meter", "pata"], "idiom", "make a mistake"),
        # Grammatical
        ("Va a comer", ["Va", "a", "comer"], "future", "going to eat"),
        ("Ha comido", ["Ha", "comido"], "perfect", "has eaten"),
        ("No sabe", ["No", "sabe"], "negation", "doesn't know"),
        ("Puede nadar", ["Puede", "nadar"], "modal", "can swim"),
    ],
    "fr": [
        # Phrasal verbs
        ("Il a mis le projet sur pied", ["mis", "sur", "pied"], "particle_verb", "set up"),
        ("Elle se rend compte de son erreur", ["rend", "compte"], "particle_verb", "realizes"),
        ("Il a donné naissance à un enfant", ["donné", "naissance"], "particle_verb", "gave birth"),
        # Idioms
        ("Il pleut des cordes", ["pleut", "cordes"], "idiom", "raining heavily"),
        ("Elle a le cafard", ["a", "cafard"], "idiom", "feeling down"),
        # Grammatical
        ("Il va partir demain", ["va", "partir"], "future", "going to leave"),
        ("Il a mangé le gâteau", ["a", "mangé"], "perfect", "has eaten"),
        ("Il ne sait pas", ["ne", "sait", "pas"], "negation", "doesn't know"),
        ("Il peut nager", ["peut", "nager"], "modal", "can swim"),
    ],
    "ro": [
        # Phrasal verbs / MWEs
        ("A dat de gol secretul", ["dat", "de", "gol"], "particle_verb", "revealed"),
        ("A luat-o la fugă", ["luat", "la", "fugă"], "particle_verb", "ran away"),
        ("Își dă seama de problemă", ["dă", "seama"], "particle_verb", "realizes"),
        # Idioms
        ("Plouă cu găleata", ["Plouă", "găleata"], "idiom", "raining heavily"),
        ("A dat din casă", ["dat", "din", "casă"], "idiom", "spilled the beans"),
        # Grammatical
        ("El va veni mâine", ["va", "veni"], "future", "will come"),
        ("El a mâncat tortul", ["a", "mâncat"], "perfect", "has eaten"),
        ("Nu știe", ["Nu", "știe"], "negation", "doesn't know"),
        ("Poate să înoate", ["Poate", "înoate"], "modal", "can swim"),
    ],
    "en": [
        # Phrasal verbs
        ("He gave up the fight", ["gave", "up"], "particle_verb", "quit"),
        ("She looked up the word", ["looked", "up"], "particle_verb", "searched"),
        ("They turned off the lights", ["turned", "off"], "particle_verb", "switched off"),
        ("He came up with an idea", ["came", "up", "with"], "particle_verb", "invented"),
        ("She put off the meeting", ["put", "off"], "particle_verb", "postponed"),
        # Idioms
        ("It's raining cats and dogs", ["raining", "cats", "dogs"], "idiom", "raining heavily"),
        ("He kicked the bucket", ["kicked", "bucket"], "idiom", "died"),
        # Grammatical
        ("He will come tomorrow", ["will", "come"], "future", "will come"),
        ("He has eaten the cake", ["has", "eaten"], "perfect", "has eaten"),
        ("He doesn't know", ["doesn't", "know"], "negation", "doesn't know"),
    ],
}

LANG_NAMES = {
    "de": "German",
    "it": "Italian",
    "es": "Spanish",
    "fr": "French",
    "ro": "Romanian",
    "en": "English",
}

# Stanza pipelines cache
_pipelines = {}

def get_stanza(lang):
    if lang not in _pipelines:
        print(f"  Loading Stanza model for {lang}...")
        _pipelines[lang] = stanza.Pipeline(
            lang=lang,
            processors='tokenize,pos,lemma,depparse',
            verbose=False
        )
    return _pipelines[lang]


def get_ms_client():
    if not MICROSOFT_KEY:
        raise ValueError("MICROSOFT_TRANSLATE_API_KEY not set")
    credential = AzureKeyCredential(MICROSOFT_KEY)
    return TextTranslationClient(credential=credential)


def analyze_example(client, sentence, mwe_words, lang):
    """Get full parse and alignment for one example"""

    # Stanza parse
    nlp = get_stanza(lang)
    doc = nlp(sentence)

    tokens = []
    compounds_found = []
    for sent in doc.sentences:
        for word in sent.words:
            head_text = sent.words[word.head - 1].text if word.head > 0 else "ROOT"
            head_pos = sent.words[word.head - 1].upos if word.head > 0 else "-"
            tokens.append({
                "text": word.text,
                "lemma": word.lemma,
                "pos": word.upos,
                "dep": word.deprel,
                "head": head_text,
                "head_pos": head_pos,
            })
            # Check for compound, aux, and negation relations
            if "compound" in word.deprel or word.deprel == "aux" or (word.upos == "PART" and word.deprel == "advmod"):
                compounds_found.append({
                    "word": word.text,
                    "relation": word.deprel,
                    "head": head_text,
                    "head_pos": head_pos,
                })

    # Microsoft alignment (translate to English)
    to_lang = "en" if lang != "en" else "de"  # English -> German for English examples
    response = client.translate(
        body=[sentence],
        to_language=[to_lang],
        from_language=lang,
        include_alignment=True,
    )

    result = response[0].translations[0]
    translation = result.text
    alignment_str = result.alignment.proj if result.alignment else ""

    # Parse alignment
    alignments = []
    if alignment_str:
        for m in alignment_str.split():
            try:
                src, tgt = m.split("-")
                src_start, src_end = map(int, src.split(":"))
                tgt_start, tgt_end = map(int, tgt.split(":"))
                src_word = sentence[src_start:src_end+1]
                tgt_word = translation[tgt_start:tgt_end+1]
                alignments.append({
                    "src": src_word,
                    "tgt": tgt_word,
                })
            except:
                continue

    # Find MWE word alignments
    mwe_alignments = {}
    for word in mwe_words:
        word_aligns = [a["tgt"] for a in alignments if a["src"].lower() == word.lower()]
        mwe_alignments[word] = word_aligns if word_aligns else ["(not aligned)"]

    return {
        "tokens": tokens,
        "compounds": compounds_found,
        "translation": translation,
        "alignment_str": alignment_str,
        "alignments": alignments,
        "mwe_alignments": mwe_alignments,
    }


def print_example(idx, sentence, mwe_words, ctype, expected, analysis, lang):
    """Print detailed analysis for one example"""

    print(f"\n{'='*80}")
    print(f"Example {idx}: [{ctype}] \"{expected}\"")
    print(f"{'='*80}")
    print(f"Source:   \"{sentence}\"")
    print(f"Target:   \"{analysis['translation']}\"")
    print(f"MWE:      {mwe_words}")

    # Stanza parse table
    print(f"\n--- Stanza Parse ---")
    print(f"{'Token':<12} {'Lemma':<12} {'POS':<6} {'Dep':<15} {'Head':<12} {'Head POS'}")
    print("-" * 70)
    for t in analysis["tokens"]:
        # Highlight MWE words and compound/aux/negation relations
        marker = ""
        if t["text"].lower() in [w.lower() for w in mwe_words]:
            marker = " ◄ MWE"
        if "compound" in t["dep"] or t["dep"] == "aux":
            marker = f" ◄ {t['dep']}"
        if t["pos"] == "PART" and t["dep"] == "advmod":
            marker = " ◄ negation"
        print(f"{t['text']:<12} {t['lemma']:<12} {t['pos']:<6} {t['dep']:<15} {t['head']:<12} {t['head_pos']}{marker}")

    # MWE relations found (compound, aux, negation)
    if analysis["compounds"]:
        print(f"\n--- MWE Relations Found ---")
        for c in analysis["compounds"]:
            print(f"  {c['word']} --[{c['relation']}]--> {c['head']} ({c['head_pos']})")
    else:
        print(f"\n--- No Compound Relations Found ---")

    # Alignment
    print(f"\n--- Microsoft Alignment ---")
    print(f"Raw: {analysis['alignment_str']}")
    print(f"\nWord mappings:")
    for a in analysis["alignments"]:
        marker = " ◄ MWE" if a["src"].lower() in [w.lower() for w in mwe_words] else ""
        print(f"  \"{a['src']}\" → \"{a['tgt']}\"{marker}")

    # MWE-specific alignments
    print(f"\n--- MWE Word Alignments ---")
    for word, targets in analysis["mwe_alignments"].items():
        multi = " (MULTI)" if len(targets) > 1 and targets[0] != "(not aligned)" else ""
        missing = " (MISSING)" if targets == ["(not aligned)"] else ""
        print(f"  {word} → {targets}{multi}{missing}")


def generate_appendix():
    print("="*80)
    print("MWE DETECTION APPENDIX - DETAILED PARSE AND ALIGNMENT DATA")
    print("="*80)
    print("\nThis appendix shows full Stanza parse and Microsoft alignment")
    print("for each example, allowing detailed investigation.\n")

    client = get_ms_client()

    for lang in ["de", "it", "es", "fr", "ro", "en"]:
        print(f"\n\n{'#'*80}")
        print(f"# {LANG_NAMES[lang].upper()} ({lang})")
        print(f"{'#'*80}")

        examples = EXAMPLES[lang]

        for idx, (sentence, mwe_words, ctype, expected) in enumerate(examples, 1):
            analysis = analyze_example(client, sentence, mwe_words, lang)
            print_example(idx, sentence, mwe_words, ctype, expected, analysis, lang)


if __name__ == "__main__":
    generate_appendix()
