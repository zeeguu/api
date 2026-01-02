"""
Test LLM-based translation alignment for MWE detection.

Compares Claude's semantic alignment with Microsoft's statistical alignment and Stanza.

Run with:
  ANTHROPIC_API_KEY="..." MICROSOFT_TRANSLATE_API_KEY="..." \
  /Users/mircea/.venvs/z_env/bin/python -m tools._mwe_llm_alignment
"""

import os
import anthropic
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text import TextTranslationClient
import stanza

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
MICROSOFT_KEY = os.environ.get("MICROSOFT_TRANSLATE_API_KEY")

# Stanza pipelines cache
_stanza_pipelines = {}

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
    "da": [
        ("Han kom op med en god idé", ["kom", "op"], "particle_verb", "came up"),
        ("Hun giver aldrig op", ["giver", "op"], "particle_verb", "gives up"),
        ("Jeg ringer dig op i morgen", ["ringer", "op"], "particle_verb", "call"),
        ("Han tager jakken på", ["tager", "på"], "particle_verb", "puts on"),
        ("Vi finder ud af det", ["finder", "ud"], "particle_verb", "figure out"),
        ("Han vil rejse i morgen", ["vil", "rejse"], "future", "will travel"),
        ("Han har læst bogen", ["har", "læst"], "perfect", "has read"),
        ("Han ved det ikke", ["ved", "ikke"], "negation", "doesn't know"),
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
    "nl": [
        # Dutch - particle verbs (similar to German)
        ("Hij staat elke dag vroeg op", ["staat", "op"], "particle_verb", "gets up"),
        ("Zij geeft nooit op", ["geeft", "op"], "particle_verb", "gives up"),
        ("Ik bel je morgen op", ["bel", "op"], "particle_verb", "call"),
        ("Hij doet het licht uit", ["doet", "uit"], "particle_verb", "turns off"),
        ("Zij trekt haar jas aan", ["trekt", "aan"], "particle_verb", "puts on"),
        # Idioms
        ("Dat is mij om het even", ["is", "mij", "even"], "idiom", "I don't care"),
        ("Ik houd mijn vingers gekruist", ["houd", "vingers", "gekruist"], "idiom", "fingers crossed"),
        # Grammatical
        ("Hij zal morgen komen", ["zal", "komen"], "future", "will come"),
        ("Hij heeft het boek gelezen", ["heeft", "gelezen"], "perfect", "has read"),
        ("Hij gaat niet naar school", ["gaat", "niet"], "negation", "doesn't go"),
    ],
    "sv": [
        # Swedish - particle verbs
        ("Han står upp tidigt varje dag", ["står", "upp"], "particle_verb", "gets up"),
        ("Hon ger aldrig upp", ["ger", "upp"], "particle_verb", "gives up"),
        ("Jag ringer dig imorgon", ["ringer"], "particle_verb", "call"),
        ("Han stänger av ljuset", ["stänger", "av"], "particle_verb", "turns off"),
        ("Hon tar på sig jackan", ["tar", "på"], "particle_verb", "puts on"),
        # Idioms
        ("Det är mig likgiltigt", ["är", "mig", "likgiltigt"], "idiom", "I don't care"),
        ("Jag håller tummarna", ["håller", "tummarna"], "idiom", "fingers crossed"),
        # Grammatical
        ("Han ska komma imorgon", ["ska", "komma"], "future", "will come"),
        ("Han har läst boken", ["har", "läst"], "perfect", "has read"),
        ("Han går inte till skolan", ["går", "inte"], "negation", "doesn't go"),
    ],
    "el": [
        # Greek - grammatical constructions (no particle verbs like Germanic)
        ("Θα έρθει αύριο", ["Θα", "έρθει"], "future", "will come"),
        ("Έχει διαβάσει το βιβλίο", ["Έχει", "διαβάσει"], "perfect", "has read"),
        ("Δεν ξέρει", ["Δεν", "ξέρει"], "negation", "doesn't know"),
        ("Μπορεί να κολυμπήσει", ["Μπορεί", "να", "κολυμπήσει"], "modal", "can swim"),
        ("Θέλω να φάω", ["Θέλω", "να", "φάω"], "modal", "want to eat"),
        # Idioms
        ("Βρέχει καρεκλοπόδαρα", ["Βρέχει", "καρεκλοπόδαρα"], "idiom", "raining heavily"),
        ("Έχω τα νεύρα μου", ["Έχω", "νεύρα"], "idiom", "I'm nervous"),
        # Perfect with auxiliary
        ("Έχω φάει", ["Έχω", "φάει"], "perfect", "have eaten"),
    ],
    "pt": [
        # Portuguese - Romance language similar to Spanish
        ("Levou a cabo o plano", ["Levou", "a", "cabo"], "particle_verb", "carried out"),
        ("Deu à luz um menino", ["Deu", "à", "luz"], "particle_verb", "gave birth"),
        ("Está chovendo canivetes", ["chovendo", "canivetes"], "idiom", "raining heavily"),
        ("Meter os pés pelas mãos", ["Meter", "pés", "mãos"], "idiom", "mess up"),
        ("Vai comer", ["Vai", "comer"], "future", "going to eat"),
        ("Tem comido", ["Tem", "comido"], "perfect", "has eaten"),
        ("Não sabe", ["Não", "sabe"], "negation", "doesn't know"),
        ("Pode nadar", ["Pode", "nadar"], "modal", "can swim"),
    ],
    "no": [
        # Norwegian - Germanic, similar to Danish/Swedish
        ("Han står opp tidlig hver dag", ["står", "opp"], "particle_verb", "gets up"),
        ("Hun gir aldri opp", ["gir", "opp"], "particle_verb", "gives up"),
        ("Jeg ringer deg i morgen", ["ringer"], "particle_verb", "call"),
        ("Han skrur av lyset", ["skrur", "av"], "particle_verb", "turns off"),
        ("Det er meg likegyldig", ["er", "meg", "likegyldig"], "idiom", "I don't care"),
        ("Han skal komme i morgen", ["skal", "komme"], "future", "will come"),
        ("Han har lest boken", ["har", "lest"], "perfect", "has read"),
        ("Han går ikke til skolen", ["går", "ikke"], "negation", "doesn't go"),
    ],
    "pl": [
        # Polish - Slavic
        ("Będzie padać jutro", ["Będzie", "padać"], "future", "will rain"),
        ("Przeczytał książkę", ["Przeczytał"], "perfect", "read"),
        ("Nie wie", ["Nie", "wie"], "negation", "doesn't know"),
        ("Może pływać", ["Może", "pływać"], "modal", "can swim"),
        ("Leje jak z cebra", ["Leje", "cebra"], "idiom", "raining heavily"),
        ("Dać nogę", ["Dać", "nogę"], "idiom", "run away"),
        ("Chcę jeść", ["Chcę", "jeść"], "modal", "want to eat"),
        ("Muszę iść", ["Muszę", "iść"], "modal", "must go"),
    ],
    "ru": [
        # Russian - Slavic
        ("Он будет читать", ["будет", "читать"], "future", "will read"),
        ("Он прочитал книгу", ["прочитал"], "perfect", "read"),
        ("Он не знает", ["не", "знает"], "negation", "doesn't know"),
        ("Он может плавать", ["может", "плавать"], "modal", "can swim"),
        ("Льёт как из ведра", ["Льёт", "ведра"], "idiom", "raining heavily"),
        ("Я хочу есть", ["хочу", "есть"], "modal", "want to eat"),
        ("Он должен идти", ["должен", "идти"], "modal", "must go"),
        ("Он умеет плавать", ["умеет", "плавать"], "modal", "knows how to swim"),
    ],
    "tr": [
        # Turkish - Turkic (agglutinative)
        ("Yarın gelecek", ["gelecek"], "future", "will come"),
        ("Kitabı okudu", ["okudu"], "perfect", "read"),
        ("Bilmiyor", ["Bilmiyor"], "negation", "doesn't know"),
        ("Yüzebilir", ["Yüzebilir"], "modal", "can swim"),
        ("Bardaktan boşanırcasına yağıyor", ["yağıyor", "boşanırcasına"], "idiom", "raining heavily"),
        ("Yemek yemek istiyorum", ["istiyorum"], "modal", "want to eat"),
        ("Gitmeli", ["Gitmeli"], "modal", "must go"),
        ("Eve gidiyor", ["gidiyor"], "progressive", "is going home"),
    ],
    "en": [
        # English - for completeness (testing reverse direction)
        ("He gave up the fight", ["gave", "up"], "particle_verb", "quit"),
        ("She looked up the word", ["looked", "up"], "particle_verb", "searched"),
        ("They turned off the lights", ["turned", "off"], "particle_verb", "switched off"),
        ("It's raining cats and dogs", ["raining", "cats", "dogs"], "idiom", "raining heavily"),
        ("He kicked the bucket", ["kicked", "bucket"], "idiom", "died"),
        ("He will come tomorrow", ["will", "come"], "future", "will come"),
        ("He has eaten the cake", ["has", "eaten"], "perfect", "has eaten"),
        ("He doesn't know", ["doesn't", "know"], "negation", "doesn't know"),
    ],
}

LANG_NAMES = {
    "de": "German", "da": "Danish", "nl": "Dutch", "sv": "Swedish", "no": "Norwegian",
    "el": "Greek", "it": "Italian", "es": "Spanish", "fr": "French", "ro": "Romanian", "pt": "Portuguese",
    "pl": "Polish", "ru": "Russian", "tr": "Turkish", "en": "English",
}


def get_stanza_pipeline(lang):
    """Get or create Stanza pipeline for a language."""
    if lang not in _stanza_pipelines:
        _stanza_pipelines[lang] = stanza.Pipeline(
            lang=lang, processors='tokenize,pos,lemma,depparse', verbose=False
        )
    return _stanza_pipelines[lang]


def check_stanza_mwe(sentence, mwe_words, lang):
    """Check if Stanza finds MWE relations between the specified words.

    Detects: compound:prt, compound, aux, and PART+advmod (negation)
    """
    nlp = get_stanza_pipeline(lang)
    doc = nlp(sentence)

    mwe_lower = [w.lower() for w in mwe_words]
    mwe_relations = []

    for sent in doc.sentences:
        for word in sent.words:
            # Check for MWE relations
            is_mwe_relation = (
                "compound" in word.deprel or
                word.deprel == "aux" or
                (word.upos == "PART" and word.deprel == "advmod")
            )

            if is_mwe_relation:
                head_text = sent.words[word.head - 1].text if word.head > 0 else "ROOT"
                # Check if both the word and its head are in MWE words
                if word.text.lower() in mwe_lower or head_text.lower() in mwe_lower:
                    mwe_relations.append({
                        "word": word.text,
                        "relation": word.deprel,
                        "head": head_text
                    })

    if mwe_relations:
        return True, mwe_relations
    return False, []


def get_llm_alignment(client, sentence, source_lang):
    """Ask Claude to translate and align with MWE grouping."""

    lang_name = LANG_NAMES[source_lang]

    prompt = f"""Translate this {lang_name} sentence to English and show word-by-word alignment.

IMPORTANT: Group multi-word expressions together on a single line:
- Particle verbs (e.g., "gibt auf" → "gives up")
- Idioms (e.g., "ist mir Wurst" → "I don't care")
- Grammatical constructions (e.g., "wird kommen" → "will come")

Format each line as: source → target

Sentence: "{sentence}"

Alignment:"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def get_ms_alignment(client, sentence, source_lang):
    """Get Microsoft Translator alignment."""

    response = client.translate(
        body=[sentence],
        to_language=["en"],
        from_language=source_lang,
        include_alignment=True,
    )

    result = response[0].translations[0]
    translation = result.text
    alignment_str = result.alignment.proj if result.alignment else ""

    # Parse alignment into word pairs
    alignments = []
    if alignment_str:
        for m in alignment_str.split():
            try:
                src, tgt = m.split("-")
                src_start, src_end = map(int, src.split(":"))
                tgt_start, tgt_end = map(int, tgt.split(":"))
                src_word = sentence[src_start:src_end+1]
                tgt_word = translation[tgt_start:tgt_end+1]
                alignments.append((src_word, tgt_word))
            except:
                continue

    return translation, alignments


def parse_llm_alignment(llm_response):
    """Parse LLM alignment response into list of (source, target) tuples."""

    alignments = []
    for line in llm_response.strip().split("\n"):
        line = line.strip()
        if "→" in line:
            parts = line.split("→")
            if len(parts) == 2:
                source = parts[0].strip()
                # Remove parenthetical notes from target
                target = parts[1].split("(")[0].strip()
                alignments.append((source, target))

    return alignments


def check_mwe_detected(alignments, mwe_words):
    """Check if MWE words appear grouped together in alignment."""

    mwe_lower = [w.lower() for w in mwe_words]

    for source, target in alignments:
        source_words = source.lower().split()
        # Check if this alignment contains multiple MWE words
        mwe_in_source = [w for w in source_words if w in mwe_lower]
        if len(mwe_in_source) >= 2:
            return True, source, target

    return False, None, None


def run_comparison():
    """Run comparison between LLM, Microsoft alignment, and Stanza."""

    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    ms_client = TextTranslationClient(credential=AzureKeyCredential(MICROSOFT_KEY))

    print("=" * 80)
    print("LLM vs MICROSOFT vs STANZA FOR MWE DETECTION")
    print("=" * 80)

    results = {
        "llm": {"detected": 0, "total": 0},
        "ms": {"detected": 0, "total": 0},
        "stanza": {"detected": 0, "total": 0}
    }

    for lang in ["de", "nl", "sv", "da", "no", "el", "pt", "it", "es", "fr", "ro", "pl", "ru", "tr", "en"]:
        print(f"\n\n{'#' * 80}")
        print(f"# {LANG_NAMES[lang].upper()}")
        print(f"{'#' * 80}")

        for sentence, mwe_words, ctype, expected in EXAMPLES[lang]:
            results["llm"]["total"] += 1
            results["ms"]["total"] += 1
            results["stanza"]["total"] += 1

            print(f"\n--- [{ctype}] \"{expected}\" ---")
            print(f"Source: {sentence}")
            print(f"MWE: {mwe_words}")

            # LLM alignment
            print(f"\n[Claude]")
            llm_response = get_llm_alignment(anthropic_client, sentence, lang)
            print(llm_response)

            llm_alignments = parse_llm_alignment(llm_response)
            llm_detected, llm_src, llm_tgt = check_mwe_detected(llm_alignments, mwe_words)

            if llm_detected:
                results["llm"]["detected"] += 1
                print(f"  ✓ MWE DETECTED: \"{llm_src}\" → \"{llm_tgt}\"")
            else:
                print(f"  ✗ MWE not grouped")

            # Microsoft alignment
            print(f"\n[Microsoft]")
            ms_translation, ms_alignments = get_ms_alignment(ms_client, sentence, lang)
            print(f"Translation: {ms_translation}")

            # Check for multi-mapping (MWE signal)
            mwe_lower = [w.lower() for w in mwe_words]
            ms_mwe_mappings = {}
            for src, tgt in ms_alignments:
                if src.lower() in mwe_lower:
                    if src not in ms_mwe_mappings:
                        ms_mwe_mappings[src] = []
                    ms_mwe_mappings[src].append(tgt)

            ms_detected = any(len(targets) > 1 for targets in ms_mwe_mappings.values())
            if ms_detected:
                results["ms"]["detected"] += 1
                multi = [(k, v) for k, v in ms_mwe_mappings.items() if len(v) > 1]
                print(f"  ✓ MWE DETECTED (multi-map): {multi}")
            else:
                print(f"  ✗ No multi-mapping for MWE words")
                print(f"  Mappings: {ms_mwe_mappings}")

            # Stanza detection
            print(f"\n[Stanza]")
            stanza_detected, stanza_relations = check_stanza_mwe(sentence, mwe_words, lang)
            if stanza_detected:
                results["stanza"]["detected"] += 1
                rels = [(r["word"], r["relation"], r["head"]) for r in stanza_relations]
                print(f"  ✓ MWE DETECTED: {rels}")
            else:
                print(f"  ✗ No MWE relation found")

    # Summary
    print(f"\n\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")

    llm_rate = results["llm"]["detected"] / results["llm"]["total"] * 100
    ms_rate = results["ms"]["detected"] / results["ms"]["total"] * 100
    stanza_rate = results["stanza"]["detected"] / results["stanza"]["total"] * 100

    print(f"\nClaude LLM:  {results['llm']['detected']}/{results['llm']['total']} = {llm_rate:.1f}%")
    print(f"Microsoft:   {results['ms']['detected']}/{results['ms']['total']} = {ms_rate:.1f}%")
    print(f"Stanza:      {results['stanza']['detected']}/{results['stanza']['total']} = {stanza_rate:.1f}%")

    # Find winner
    rates = [("LLM", llm_rate), ("Microsoft", ms_rate), ("Stanza", stanza_rate)]
    rates.sort(key=lambda x: x[1], reverse=True)
    winner, winner_rate = rates[0]
    second, second_rate = rates[1]

    print(f"\n→ {winner} leads with {winner_rate:.1f}%")
    print(f"→ {winner} outperforms {second} by {winner_rate - second_rate:.1f} percentage points")


if __name__ == "__main__":
    run_comparison()
