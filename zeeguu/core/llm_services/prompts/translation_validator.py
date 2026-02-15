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

STEP 1 - VALIDATION:
1. Is "{word}" a meaningful learning unit? (Not an arbitrary fragment like "bruger den" = "are using it")
2. Is "{translation}" a correct translation for the WORD itself (not the surrounding phrase)?
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

Reply in this EXACT format (one line):
VALID|frequency|cefr|phrase_type|explanation|literal_meaning
or
FIX|corrected_word|corrected_translation|frequency|cefr|phrase_type|reason|explanation|literal_meaning

Fields:
- cefr: A1, A2, B1, B2, C1, or C2
- explanation: OPTIONAL usage notes, register (formal/informal). Leave empty if not needed.
- literal_meaning: ONLY for idioms - SHORT word-by-word translation (e.g., "kick into touch").
  Leave EMPTY for single words, collocations, and non-idioms. NOT for explanations!

Examples:
- Simple word: VALID|common|A1|single_word||
- Word with usage note: VALID|common|B1|single_word|formal register|
- Idiom: VALID|common|B2|idiom||kick into touch
- Wrong translation: FIX|øjnene|the eyes|common|A2|single_word|literal meaning is 'the eyes'||
- Idiom fix: FIX|se virkeligheden i øjnene|face reality|common|B2|idiom|idiom meaning 'face reality'||see reality in the eyes
- Arbitrary fragment: FIX|bruger|use|common|A2|single_word|'bruger den' is arbitrary fragment||
"""


# Batch version for prefetch efficiency
BATCH_VALIDATION_PROMPT = """Validate and classify these language learning translations.

For each entry:
1. Check if the word is a meaningful learning unit (not an arbitrary fragment)
2. Check if the translation is correct for the word (not influenced by idiomatic context)
3. Classify frequency (unique/common/uncommon/rare) and phrase_type (single_word/collocation/idiom/expression/arbitrary_multi_word)

Entries:
{entries}

Reply with ONE line per entry in this EXACT format:
VALID|frequency|phrase_type
or
FIX|corrected_word|corrected_translation|frequency|phrase_type|reason

No numbering, no explanations, just the results in order."""


def create_combined_validation_prompt(word, translation, context, source_lang, target_lang):
    """Create prompt for combined validation + classification."""
    return COMBINED_VALIDATION_PROMPT.format(
        word=word,
        translation=translation,
        context=context,
        source_lang=source_lang,
        target_lang=target_lang
    )


def create_batch_validation_prompt(items):
    """
    Create batch prompt for validating multiple translations.

    Args:
        items: List of dicts with keys: word, translation, context, source_lang, target_lang

    Returns:
        str: Formatted batch prompt
    """
    entries = []
    for i, item in enumerate(items, 1):
        entry = f'{i}. "{item["word"]}" ({item["source_lang"]}) -> "{item["translation"]}" ({item["target_lang"]})\n   Context: "{item["context"]}"'
        entries.append(entry)

    return BATCH_VALIDATION_PROMPT.format(entries="\n".join(entries))


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
