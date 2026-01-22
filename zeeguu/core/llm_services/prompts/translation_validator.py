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
- "by" for "ved at" is VALID (even if "by doing" is more complete)
- Keep translations SHORT and SIMPLE - learners must type them in exercises
- NO parenthetical explanations like "by (doing something)" - just "by"
- NO articles unless essential: "eyes" not "the eyes"

STEP 2 - CLASSIFICATION (for the valid/corrected word):
Frequency:
- unique: only meaning of the word
- common: primary or frequently used meaning
- uncommon: infrequently used meaning
- rare: specialized, archaic, or context-specific

Phrase type:
- single_word: individual word
- collocation: natural word combination ("strong coffee", "take place")
- idiom: non-literal meaning ("break the ice", "piece of cake")
- expression: common phrase/greeting ("how are you")
- arbitrary_multi_word: random fragment, NOT worth studying ("doctor for", "the cat on", "bruger den")

Reply in this EXACT format (one line):
VALID|frequency|phrase_type|explanation
or
FIX|corrected_word|corrected_translation|frequency|phrase_type|reason|explanation

The explanation field is OPTIONAL - leave empty unless truly helpful.
ONLY use for: usage nuances, register (formal/informal), or non-obvious context.
Do NOT include: grammar parsing, conjugation info, or obvious facts.

Examples:
- Simple word: VALID|common|single_word|
- Word with usage note: VALID|common|single_word|used with verbs to indicate manner
- Wrong translation "øjnene" -> "in the face": FIX|øjnene|the eyes|common|single_word|literal meaning is 'the eyes'|
- Idiom worth learning: FIX|se virkeligheden i øjnene|face reality|common|idiom|idiom meaning 'face reality'|literally 'see reality in the eyes'
- Arbitrary fragment: FIX|bruger|use|common|single_word|'bruger den' is arbitrary fragment|
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
