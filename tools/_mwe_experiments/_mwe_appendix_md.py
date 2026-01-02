"""
Generate detailed appendix for MWE report in Markdown format.

Run with:
  MICROSOFT_TRANSLATE_API_KEY="..." /Users/mircea/.venvs/z_env/bin/python -m tools._mwe_appendix_md
"""

import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text import TextTranslationClient
import stanza

MICROSOFT_KEY = os.environ.get("MICROSOFT_TRANSLATE_API_KEY")

EXAMPLES = {
    "de": [
        ("Ich rufe dich morgen an", ["rufe", "an"], "particle_verb", "call"),
        ("Er steht jeden Tag früh auf", ["steht", "auf"], "particle_verb", "gets up"),
        ("Sie gibt niemals auf", ["gibt", "auf"], "particle_verb", "gives up"),
        ("Er macht das Licht aus", ["macht", "aus"], "particle_verb", "turns off"),
        ("Sie zieht sich warm an", ["zieht", "an"], "particle_verb", "dresses"),
        ("Das ist mir Wurst", ["ist", "mir", "Wurst"], "idiom", "I don't care"),
        ("Ich drücke dir die Daumen", ["drücke", "die", "Daumen"], "idiom", "fingers crossed"),
        ("Er wird morgen kommen", ["wird", "kommen"], "future", "will come"),
        ("Er hat das Buch gelesen", ["hat", "gelesen"], "perfect", "has read"),
        ("Er geht nicht zur Schule", ["geht", "nicht"], "negation", "doesn't go"),
    ],
    "it": [
        ("Lui ha messo in piedi il progetto", ["messo", "in", "piedi"], "particle_verb", "set up"),
        ("Lei si rende conto del problema", ["rende", "conto"], "particle_verb", "realizes"),
        ("Hanno dato alla luce un bambino", ["dato", "alla", "luce"], "particle_verb", "gave birth"),
        ("Piove a catinelle", ["Piove", "catinelle"], "idiom", "raining heavily"),
        ("Ho le mani in pasta", ["ho", "mani", "pasta"], "idiom", "involved in"),
        ("Lui andrà domani", ["andrà"], "future", "will go"),
        ("Lui ha mangiato la torta", ["ha", "mangiato"], "perfect", "has eaten"),
        ("Non so", ["Non", "so"], "negation", "don't know"),
        ("Lui può nuotare", ["può", "nuotare"], "modal", "can swim"),
    ],
    "es": [
        ("Llevó a cabo el plan", ["Llevó", "a", "cabo"], "particle_verb", "carried out"),
        ("Dio a luz a un niño", ["Dio", "a", "luz"], "particle_verb", "gave birth"),
        ("Echó de menos a su amigo", ["Echó", "de", "menos"], "particle_verb", "missed"),
        ("Está lloviendo a cántaros", ["lloviendo", "cántaros"], "idiom", "raining heavily"),
        ("Meter la pata", ["Meter", "pata"], "idiom", "make a mistake"),
        ("Va a comer", ["Va", "a", "comer"], "future", "going to eat"),
        ("Ha comido", ["Ha", "comido"], "perfect", "has eaten"),
        ("No sabe", ["No", "sabe"], "negation", "doesn't know"),
        ("Puede nadar", ["Puede", "nadar"], "modal", "can swim"),
    ],
    "fr": [
        ("Il a mis le projet sur pied", ["mis", "sur", "pied"], "particle_verb", "set up"),
        ("Elle se rend compte de son erreur", ["rend", "compte"], "particle_verb", "realizes"),
        ("Il a donné naissance à un enfant", ["donné", "naissance"], "particle_verb", "gave birth"),
        ("Il pleut des cordes", ["pleut", "cordes"], "idiom", "raining heavily"),
        ("Elle a le cafard", ["a", "cafard"], "idiom", "feeling down"),
        ("Il va partir demain", ["va", "partir"], "future", "going to leave"),
        ("Il a mangé le gâteau", ["a", "mangé"], "perfect", "has eaten"),
        ("Il ne sait pas", ["ne", "sait", "pas"], "negation", "doesn't know"),
        ("Il peut nager", ["peut", "nager"], "modal", "can swim"),
    ],
    "ro": [
        ("A dat de gol secretul", ["dat", "de", "gol"], "particle_verb", "revealed"),
        ("A luat-o la fugă", ["luat", "la", "fugă"], "particle_verb", "ran away"),
        ("Își dă seama de problemă", ["dă", "seama"], "particle_verb", "realizes"),
        ("Plouă cu găleata", ["Plouă", "găleata"], "idiom", "raining heavily"),
        ("A dat din casă", ["dat", "din", "casă"], "idiom", "spilled the beans"),
        ("El va veni mâine", ["va", "veni"], "future", "will come"),
        ("El a mâncat tortul", ["a", "mâncat"], "perfect", "has eaten"),
        ("Nu știe", ["Nu", "știe"], "negation", "doesn't know"),
        ("Poate să înoate", ["Poate", "înoate"], "modal", "can swim"),
    ],
    "en": [
        ("He gave up the fight", ["gave", "up"], "particle_verb", "quit"),
        ("She looked up the word", ["looked", "up"], "particle_verb", "searched"),
        ("They turned off the lights", ["turned", "off"], "particle_verb", "switched off"),
        ("He came up with an idea", ["came", "up", "with"], "particle_verb", "invented"),
        ("She put off the meeting", ["put", "off"], "particle_verb", "postponed"),
        ("It's raining cats and dogs", ["raining", "cats", "dogs"], "idiom", "raining heavily"),
        ("He kicked the bucket", ["kicked", "bucket"], "idiom", "died"),
        ("He will come tomorrow", ["will", "come"], "future", "will come"),
        ("He has eaten the cake", ["has", "eaten"], "perfect", "has eaten"),
        ("He doesn't know", ["doesn't", "know"], "negation", "doesn't know"),
    ],
}

LANG_NAMES = {
    "de": "German", "it": "Italian", "es": "Spanish",
    "fr": "French", "ro": "Romanian", "en": "English",
}

_pipelines = {}

def get_stanza(lang):
    if lang not in _pipelines:
        _pipelines[lang] = stanza.Pipeline(lang=lang, processors='tokenize,pos,lemma,depparse', verbose=False)
    return _pipelines[lang]

def get_ms_client():
    credential = AzureKeyCredential(MICROSOFT_KEY)
    return TextTranslationClient(credential=credential)

def analyze_example(client, sentence, mwe_words, lang):
    nlp = get_stanza(lang)
    doc = nlp(sentence)

    tokens = []
    compounds_found = []
    for sent in doc.sentences:
        for word in sent.words:
            head_text = sent.words[word.head - 1].text if word.head > 0 else "ROOT"
            head_pos = sent.words[word.head - 1].upos if word.head > 0 else "-"
            tokens.append({
                "text": word.text, "lemma": word.lemma, "pos": word.upos,
                "dep": word.deprel, "head": head_text, "head_pos": head_pos,
            })
            if "compound" in word.deprel or word.deprel == "aux" or (word.upos == "PART" and word.deprel == "advmod"):
                compounds_found.append({
                    "word": word.text, "relation": word.deprel,
                    "head": head_text, "head_pos": head_pos,
                })

    to_lang = "en" if lang != "en" else "de"
    response = client.translate(body=[sentence], to_language=[to_lang], from_language=lang, include_alignment=True)
    result = response[0].translations[0]
    translation = result.text
    alignment_str = result.alignment.proj if result.alignment else ""

    alignments = []
    if alignment_str:
        for m in alignment_str.split():
            try:
                src, tgt = m.split("-")
                src_start, src_end = map(int, src.split(":"))
                tgt_start, tgt_end = map(int, tgt.split(":"))
                alignments.append({"src": sentence[src_start:src_end+1], "tgt": translation[tgt_start:tgt_end+1]})
            except:
                continue

    mwe_alignments = {}
    for word in mwe_words:
        word_aligns = [a["tgt"] for a in alignments if a["src"].lower() == word.lower()]
        mwe_alignments[word] = word_aligns if word_aligns else None

    return {
        "tokens": tokens, "compounds": compounds_found, "translation": translation,
        "alignment_str": alignment_str, "alignments": alignments, "mwe_alignments": mwe_alignments,
    }

def print_example_md(idx, sentence, mwe_words, ctype, expected, analysis, lang):
    print(f"\n### {idx}. [{ctype}] \"{expected}\"\n")
    print(f"**Source:** `{sentence}`\n")
    print(f"**Target:** `{analysis['translation']}`\n")
    print(f"**MWE words:** {mwe_words}\n")

    # Stanza parse table
    print("#### Stanza Parse\n")
    print("| Token | Lemma | POS | Dep | Head | Note |")
    print("|-------|-------|-----|-----|------|------|")
    for t in analysis["tokens"]:
        note = ""
        if t["text"].lower() in [w.lower() for w in mwe_words]:
            note = "**MWE**"
        if "compound" in t["dep"] or t["dep"] == "aux":
            note = f"**{t['dep']}**"
        if t["pos"] == "PART" and t["dep"] == "advmod":
            note = f"**negation**"
        print(f"| {t['text']} | {t['lemma']} | {t['pos']} | {t['dep']} | {t['head']} | {note} |")

    # MWE relations found (compound:prt, compound, aux, negation)
    if analysis["compounds"]:
        print("\n#### MWE Relations Found\n")
        for c in analysis["compounds"]:
            print(f"- `{c['word']}` --[**{c['relation']}**]--> `{c['head']}` ({c['head_pos']})")
    else:
        print("\n#### MWE Relations: None found\n")

    # Alignment
    print("\n#### Microsoft Alignment\n")
    print(f"**Raw:** `{analysis['alignment_str']}`\n")
    print("| Source | Target | Note |")
    print("|--------|--------|------|")
    for a in analysis["alignments"]:
        note = "**MWE**" if a["src"].lower() in [w.lower() for w in mwe_words] else ""
        print(f"| {a['src']} | {a['tgt']} | {note} |")

    # MWE alignments summary
    print("\n#### MWE Detection Summary\n")
    print("| Word | Alignment | Status |")
    print("|------|-----------|--------|")
    for word, targets in analysis["mwe_alignments"].items():
        if targets is None:
            print(f"| {word} | (none) | **MISSING** |")
        elif len(targets) > 1:
            print(f"| {word} | {targets} | **MULTI** |")
        else:
            print(f"| {word} | {targets} | single |")

def generate_appendix():
    print("# MWE Detection Appendix\n")
    print("Detailed Stanza parse and Microsoft alignment data for each example.\n")
    print("---\n")

    client = get_ms_client()

    for lang in ["de", "it", "es", "fr", "ro", "en"]:
        print(f"\n## {LANG_NAMES[lang]} ({lang})\n")

        for idx, (sentence, mwe_words, ctype, expected) in enumerate(EXAMPLES[lang], 1):
            analysis = analyze_example(client, sentence, mwe_words, lang)
            print_example_md(idx, sentence, mwe_words, ctype, expected, analysis, lang)
            print("\n---\n")

if __name__ == "__main__":
    generate_appendix()
