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

This pair becomes a FLASHCARD. The learner will memorize "{word}" = "{translation}"
and be quizzed on it in vocabulary exercises, often in OTHER sentences.

STEP 1 - VALIDATION:
1. Is "{word}" a meaningful learning unit? (Not an arbitrary fragment like "bruger den" = "are using it")
2. Is "{translation}" a correct translation for the WORD itself (not the surrounding phrase)?
   Test: if the learner memorizes this pair and later meets "{word}" in an ordinary sentence,
   does the translation still hold? If it only works because of the surrounding phrase, it is
   NOT valid: either translate the word's own meaning, or expand the word to the phrase that
   carries the meaning.
3. If the word is part of an idiom, decide: should the learner study the single word or the full idiom?

IMPORTANT: Only mark as FIX if the translation is WRONG. Do NOT "improve" correct translations.
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

Fill in these fields (the reply is constrained to this shape):
- reason: one short sentence, written first: why the pair holds, or what is wrong with it
- verdict: VALID or FIX
- corrected_word, corrected_translation: the corrected pair when the verdict is FIX, empty when
  VALID. corrected_translation is in {target_lang}.
- frequency, cefr, phrase_type: for the valid or corrected word (STEP 2)
- explanation: OPTIONAL usage notes, register (formal/informal). Empty if not needed.
- literal_meaning: ONLY for idioms - SHORT word-by-word translation (e.g., "kick into touch").
  Empty for single words, collocations, and non-idioms. NOT for explanations!

Examples:
- Simple word: VALID, common, A1, single_word
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
        "reason",
        "verdict",
        "corrected_word",
        "corrected_translation",
        "frequency",
        "cefr",
        "phrase_type",
        "explanation",
        "literal_meaning",
    ],
    "properties": {
        "reason": {"type": "string"},
        "verdict": {"type": "string", "enum": ["VALID", "FIX"]},
        "corrected_word": {"type": "string"},
        "corrected_translation": {"type": "string"},
        "frequency": {"type": "string", "enum": ["unique", "common", "uncommon", "rare"]},
        "cefr": {"type": "string", "enum": ["A1", "A2", "B1", "B2", "C1", "C2"]},
        "phrase_type": {
            "type": "string",
            "enum": ["single_word", "collocation", "idiom", "expression", "arbitrary_multi_word"],
        },
        "explanation": {"type": "string"},
        "literal_meaning": {"type": "string"},
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
