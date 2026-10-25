"""
Prompt templates for combined translation validation and classification.

This validates that a translation is correct for the specific word,
and classifies its frequency and phrase type - all in a single LLM call.
"""

COMBINED_VALIDATION_PROMPT = """You are validating and classifying a language learning translation.

A learner highlighted "{word}" in this {source_lang} sentence:
"{context}"

The translation is in {target_lang}: "{translation}"

CRITICAL: The translation "{translation}" is in {target_lang}, NOT English!
If {target_lang} is Dutch, German, etc., interpret the translation IN THAT LANGUAGE.
Example: "offer" in Dutch means "victim/sacrifice" - this is VALID for "víctima" (Spanish).

This pair becomes a FLASHCARD. Exercises show THIS sentence with "{word}" highlighted and
"{translation}" written above it, and later quiz the pair in other sentences too.

STEP 1 - VALIDATION:
1. Is the sentence usable? If it is cut off, ungrammatical, or does not make sense, no card
   can be checked against it: the verdict is UNRESOLVED.
2. Does "{translation}" fit THIS sentence? Read the sentence with "{translation}" in place of
   "{word}": it must say what the sentence says, in correct {target_lang}. The form must be
   the one the sentence needs - tense, number, person ("sov" in "hun sov længe" = "slept", not
   "sleep"; "biler" in "to biler" = "cars"). {target_lang} may add words around it that
   {source_lang} does not need ("does", "not", an article): "Hvad betyder det?" = "What does it
   mean?", so "betyder" = "mean" fits there.
3. Is it the meaning of "{word}" itself, not of the surrounding phrase? It should still hold
   when the learner meets "{word}" in an ordinary sentence. If it only works because of the
   surrounding phrase, expand "{word}" to the smallest expression in the sentence that carries
   the meaning ("holde øje med" = "keep an eye on"), as long as that expression is worth learning on its
   own. Never expand to an arbitrary fragment like "bruger den" = "are using it".
4. A verb without its infinitive marker (Danish "at", German "zu", Dutch "te", Swedish "att",
   ...) is translated without "to": "verstehen" = "understand", NOT "to understand". With the
   marker, keep it: "at slå op" = "to look up".
5. If no translation fits the sentence and no expansion gives an expression worth learning,
   the verdict is UNRESOLVED. Say why in the reason.

A corrected word must appear in the sentence exactly as written there: every one of its words,
in the sentence's own spelling. Never correct the sentence's grammar into the word.

IMPORTANT: VALID when "{translation}" fits the sentence and is the meaning of "{word}", even if
another translation is more common: "med" in "hun kom med toget" = "by". Only FIX what is
WRONG (in meaning, form or unit). Do NOT "improve" correct translations.
- Keep translations SHORT and SIMPLE - learners must type them in exercises
- NO parenthetical explanations like "by (doing something)" - just "by"
- NO alternatives with "/" like "as/in the capacity of" - pick ONE: "as"
- NO articles unless essential: "eyes" not "the eyes"

STEP 2 - CLASSIFICATION (for the valid/corrected word):
Frequency:
- unique: only meaning of the word
- common: primary or frequently used meaning
- uncommon: infrequently used meaning
- rare: specialized, archaic, or context-specific

CEFR Level (what level learner should know this word):
- A1: basic everyday words (hello, cat, eat)
- A2: common everyday vocabulary (weather, shopping)
- B1: intermediate topics (opinions, work, travel)
- B2: abstract concepts, nuanced vocabulary
- C1: advanced, sophisticated vocabulary
- C2: rare, literary, highly specialized

Phrase type:
- single_word: individual word
- collocation: natural word combination ("strong coffee", "take place")
- idiom: non-literal meaning ("break the ice", "piece of cake")
- expression: common phrase/greeting ("how are you")
- arbitrary_multi_word: random fragment, NOT worth studying ("doctor for", "the cat on", "bruger den")

STEP 3 - DICTIONARY CASE (for the valid/corrected pair):
Write the word and its translation as a dictionary would: lowercase, unless the language
capitalizes them anyway (German nouns, proper nouns, English days, months, languages and
nationalities, the pronoun "I"). Standing at the start of the sentence is NOT a reason to
capitalize. Case alone never makes a pair FIX.

Fill in these fields (the reply is constrained to this shape):
- card_in_sentence: the sentence translated into natural {target_lang}, with "{translation}"
  written exactly as it is in place of "{word}". Around it, write what {target_lang} needs
  ("doesn't", "does", articles, word order: "Hun forstår ikke" = "She doesn't understand");
  only "{translation}" itself must not change form to make it fit.
- card_reads_right: true only if card_in_sentence is correct, natural {target_lang} that says
  what the sentence says. A wrong verb form ("what it mean") is false. If false, the verdict
  cannot be VALID.
- reason: one short sentence, written first: why the pair holds, or what is wrong with it
- verdict: VALID, FIX or UNRESOLVED
- corrected_word, corrected_translation: the corrected pair when the verdict is FIX, empty when
  VALID or UNRESOLVED. corrected_translation is in {target_lang}.
- correction_in_sentence: for a FIX, the {target_lang} sentence again, now with
  corrected_translation written exactly as it is in place of corrected_word, the rest natural
  {target_lang} as above. Empty when VALID or UNRESOLVED.
- correction_reads_right: true only if correction_in_sentence is correct, natural {target_lang}.
  If false, your correction is wrong too: change corrected_translation. False when not a FIX.
- frequency, cefr, phrase_type: for the valid or corrected word (STEP 2)
- explanation: OPTIONAL usage notes, register (formal/informal). Empty if not needed.
- literal_meaning: ONLY for idioms - SHORT word-by-word translation (e.g., "kick into touch").
  Empty for single words, collocations, and non-idioms. NOT for explanations!
- dictionary_word, dictionary_translation: the valid or corrected pair in dictionary case (STEP 3)

Examples:
- Simple word: VALID, common, A1, single_word
- Sentence-initial word: "Dette" = "This" is VALID, common, A1, single_word, dictionary pair dette = "this";
  "Mandag" = "Monday" gives mandag = "Monday"; German "Haus" = "house" gives Haus = "house"
- Wrong form: glemme = "to forget" becomes FIX glemme = "forget", common, A2, single_word;
  reason: the highlighted word has no "at", so the translation must not have "to"
- Word with usage note: VALID, common, B1, single_word, explanation "formal register"
- Idiom: VALID, common, B2, idiom, literal_meaning "kick into touch"
- Wrong translation: FIX øjnene = "the eyes", common, A2, single_word; reason: literal meaning is 'the eyes'
- Idiom fix: FIX se virkeligheden i øjnene = "face reality", common, B2, idiom, literal_meaning "see reality in the eyes"
- Arbitrary fragment: FIX bruger = "use", common, A2, single_word; reason: 'bruger den' is an arbitrary fragment
- Context-only gloss: FIX noget af = "one of", common, B1, collocation, literal_meaning "something of";
  reason: 'noget' alone means 'something'; 'one' only holds inside 'noget af'
"""


# Appended when a reply's translation lists options; see TranslationValidator.
SINGLE_TRANSLATION_REMINDER = """

The translation "{translation}" lists options. A flashcard needs ONE translation
the learner can type: no alternatives with "/", no explanation in parentheses.
Reply FIX with the single translation that fits this sentence best.
"""


# The reply shape for COMBINED_VALIDATION_PROMPT, enforced by the API through
# structured outputs: with thinking off, Sonnet 5.5 often wrote its reasoning
# before the requested one-line format, and ran out of tokens before reaching
# it (22 of 50 prod cases). `reason` comes first so the short reasoning it
# wants to do lands in a field instead of in front of the answer.
VALIDATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "card_in_sentence",
        "card_reads_right",
        "reason",
        "verdict",
        "corrected_word",
        "corrected_translation",
        "correction_in_sentence",
        "correction_reads_right",
        "frequency",
        "cefr",
        "phrase_type",
        "explanation",
        "literal_meaning",
        "dictionary_word",
        "dictionary_translation",
    ],
    "properties": {
        "card_in_sentence": {"type": "string"},
        "card_reads_right": {"type": "boolean"},
        "reason": {"type": "string"},
        "verdict": {"type": "string", "enum": ["VALID", "FIX", "UNRESOLVED"]},
        "corrected_word": {"type": "string"},
        "corrected_translation": {"type": "string"},
        "correction_in_sentence": {"type": "string"},
        "correction_reads_right": {"type": "boolean"},
        "frequency": {"type": "string", "enum": ["unique", "common", "uncommon", "rare"]},
        "cefr": {"type": "string", "enum": ["A1", "A2", "B1", "B2", "C1", "C2"]},
        "phrase_type": {
            "type": "string",
            "enum": ["single_word", "collocation", "idiom", "expression", "arbitrary_multi_word"],
        },
        "explanation": {"type": "string"},
        "literal_meaning": {"type": "string"},
        "dictionary_word": {"type": "string"},
        "dictionary_translation": {"type": "string"},
    },
}


def create_combined_validation_prompt(word, translation, context, source_lang, target_lang):
    """Create prompt for combined validation + classification."""
    return COMBINED_VALIDATION_PROMPT.format(
        word=word,
        translation=translation,
        context=context,
        source_lang=source_lang,
        target_lang=target_lang
    )


SEMANTIC_EQUIVALENCE_PROMPT = """Are these two translations of the same word semantically equivalent?

Word: "{word}" ({source_lang})
Translation 1: "{translation1}" ({target_lang})
Translation 2: "{translation2}" ({target_lang})

Consider them equivalent if:
- They mean the same thing (e.g., "to cancel" and "cancel")
- One is just a grammatical variation of the other (infinitive vs base form)
- They are synonyms in this context

Reply with ONLY one word: YES or NO"""


def create_semantic_equivalence_prompt(word, translation1, translation2, source_lang, target_lang):
    """Create prompt for checking if two translations are semantically equivalent."""
    return SEMANTIC_EQUIVALENCE_PROMPT.format(
        word=word,
        translation1=translation1,
        translation2=translation2,
        source_lang=source_lang,
        target_lang=target_lang
    )


# Appended when the reply's own check says its card does not fit: it wrote
# "what it mean to walk", marked that false, and kept "mean" anyway (it cannot
# go back once later fields are written). See TranslationValidator._misfit.
CARD_DOES_NOT_FIT_REMINDER = """

In a previous answer you proposed "{card}" and wrote the sentence as "{sentence}".
{problem} Reply again. The card must be exactly the form that makes the sentence read right;
if no form of a worthwhile word or expression does, the verdict is UNRESOLVED.
"""
