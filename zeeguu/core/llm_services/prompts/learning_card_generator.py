"""
Prompt for generating an optimal learning card from a word lookup.

Takes a searched word, translation, and example sentences,
and returns the best word form, translation, and example for learning.
"""

LEARNING_CARD_PROMPT = """You are helping a language learner add a word to their study deck.

The learner searched for "{searched_word}" in {source_lang}.
They want to learn the translation "{translation}" in {target_lang}.
Their level is {cefr_level}.

Here are example sentences showing the word in use:
{examples}

Your task: Prepare the best learning card for this word.

CRITICAL RULE - WORD FORM MUST MATCH EXAMPLE:
The word form you return MUST appear EXACTLY in the example sentence you choose.
This is required for the system to highlight and track the word correctly.

Steps:
1. Look at the example sentences
2. Find the word form actually used (e.g., "ophæve" not "ophæv")
3. Return THAT exact form as the WORD
4. The EXAMPLE must contain that exact word

MULTI-WORD EXPRESSIONS (MWE):
If the learner searched for multiple words (e.g., "ophæv spærret"):
- Decide: is it better to learn the MWE as a unit, or individual words?
- For idioms/fixed expressions: keep as MWE
- For word combinations that aren't fixed: recommend the most useful individual word
- Set RECOMMENDATION to explain your choice

TRANSLATION: Keep it simple and typeable (learner must type this in exercises):
- Short and direct
- No parenthetical explanations
- No alternatives with "/"
- For verbs: include "to" (e.g., "to cancel" not "cancel")

EXPLANATION: Write a brief, helpful note about this word/meaning:
- 1-2 sentences max
- Mention if it's formal/informal, common/rare
- Note any tricky aspects (false friends, multiple meanings, etc.)
- Write in {target_lang} so the learner can understand it

LEVEL CHECK: Is this word appropriate for a {cefr_level} learner?
- Consider: word frequency, complexity, usefulness
- If it's above their level, mention it but still allow learning (exposure is good)

Reply in this EXACT format (7 lines):
WORD: [exact word form as it appears in the example]
TRANSLATION: [simple translation]
EXAMPLE: [example sentence containing the exact word]
EXAMPLE_TRANSLATION: [translation of the example sentence]
EXPLANATION: [brief helpful note about this meaning]
LEVEL_NOTE: [appropriate/challenging/advanced for {cefr_level}, with brief reason]
RECOMMENDATION: [for MWEs: "learn as MWE" or "learn X instead" with reason; for single words: "recommended"]

Example for single word:
WORD: ophæve
TRANSLATION: to cancel
EXAMPLE: Jeg vil gerne ophæve min reservation.
EXAMPLE_TRANSLATION: I would like to cancel my reservation.
EXPLANATION: Common verb for canceling subscriptions, reservations, or agreements. Slightly formal.
LEVEL_NOTE: appropriate for B1 - useful everyday vocabulary
RECOMMENDATION: recommended

Example for MWE where individual word is better:
WORD: ophæve
TRANSLATION: to cancel/lift
EXAMPLE: Banken kan ophæve spærret konto.
EXAMPLE_TRANSLATION: The bank can unblock the blocked account.
EXPLANATION: "Ophæve" means to cancel, lift, or remove. Very versatile verb.
LEVEL_NOTE: appropriate for B1 - useful verb with many applications
RECOMMENDATION: learn "ophæve" instead of "ophæv spærret" - "ophæve" is more versatile and "spærret" (blocked) can be learned separately
"""


def create_learning_card_prompt(
    searched_word,
    translation,
    source_lang,
    target_lang,
    cefr_level,
    examples
):
    """Create prompt for generating an optimal learning card."""
    # Format examples as numbered list
    if examples:
        examples_text = "\n".join(f"{i+1}. {ex}" for i, ex in enumerate(examples))
    else:
        examples_text = "(no examples provided - please generate one)"

    return LEARNING_CARD_PROMPT.format(
        searched_word=searched_word,
        translation=translation,
        source_lang=source_lang,
        target_lang=target_lang,
        cefr_level=cefr_level,
        examples=examples_text
    )


def parse_learning_card_response(response_text):
    """
    Parse the LLM response into structured data.

    Returns dict with keys: word, translation, example, example_translation,
                           explanation, level_note
    Or None if parsing fails.
    """
    lines = response_text.strip().split("\n")
    result = {}

    for line in lines:
        line = line.strip()
        if line.startswith("WORD:"):
            result["word"] = line[5:].strip()
        elif line.startswith("TRANSLATION:"):
            result["translation"] = line[12:].strip()
        elif line.startswith("EXAMPLE:"):
            result["example"] = line[8:].strip()
        elif line.startswith("EXAMPLE_TRANSLATION:"):
            result["example_translation"] = line[20:].strip()
        elif line.startswith("EXPLANATION:"):
            result["explanation"] = line[12:].strip()
        elif line.startswith("LEVEL_NOTE:"):
            result["level_note"] = line[11:].strip()
        elif line.startswith("RECOMMENDATION:"):
            result["recommendation"] = line[15:].strip()

    # Validate we got all required fields
    required = ["word", "translation", "example"]
    if all(key in result for key in required):
        return result

    return None
