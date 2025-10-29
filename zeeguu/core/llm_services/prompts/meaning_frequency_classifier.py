"""
Prompt for classifying meaning frequency and phrase type using Anthropic API.
Designed to return only the classifications with minimal token usage.
Supports both single and batch classification.
"""

BATCH_MEANING_FREQUENCY_AND_TYPE_PROMPT = """Classify these word/phrase meanings by frequency and type.

Entries to classify:
{entries}

Frequency categories:
- unique: only meaning
- common: the word has multiple meanings, and this is one of frequently used ones (primary meaning)
- uncommon: the word has multiple meanings, and this particular one is infrequently used
- rare: rarely used meaning (specialized, archaic, or very context-specific)

Phrase type categories:
- single_word: individual word
- collocation: natural word combination (e.g., "strong coffee", "take place")
- idiom: idiomatic expression with non-literal meaning (e.g., "break the ice", "piece of cake")
- expression: common phrase/greeting (e.g., "how are you", "thank you very much")
- arbitrary_multi_word: NOT a good unit of study - random word combinations that should be studied separately (e.g., "doctor for", "the cat on", "walked slowly towards")

Reply with ONLY one line per entry: frequency,phrase_type (e.g., "common,single_word")
No explanations, no numbering, just the classifications."""

# Legacy single-item prompt (now just uses batch with N=1)
MEANING_FREQUENCY_AND_TYPE_PROMPT = """Classify this word/phrase meaning frequency and type.

Word/Phrase: {origin_word}
Language: {origin_language}
Translation: {translation_word}
Target language: {translation_language}

Frequency categories:
- unique: only meaning
- common: the word has multiple meanings, and this is one of frequently used ones (primary meaning)
- uncommon: the word has multiple meanings, and this particular one is infrequently used
- rare: rarely used meaning (specialized, archaic, or very context-specific)

Phrase type categories:
- single_word: individual word
- collocation: natural word combination (e.g., "strong coffee", "take place")
- idiom: idiomatic expression with non-literal meaning (e.g., "break the ice", "piece of cake")
- expression: common phrase/greeting (e.g., "how are you", "thank you very much")
- arbitrary_multi_word: NOT a good unit of study - random word combinations that should be studied separately (e.g., "doctor for", "the cat on", "walked slowly towards")

Reply with ONLY: frequency,phrase_type (e.g., "common,single_word")"""


def create_batch_meaning_frequency_and_type_prompt(meanings):
    """
    Create a batch prompt to classify multiple meanings at once.

    Args:
        meanings: List of Meaning objects with origin and translation

    Returns:
        str: Formatted batch prompt ready for API call
    """
    entries = []
    for i, meaning in enumerate(meanings, 1):
        entry = f'{i}. "{meaning.origin.content}" ({meaning.origin.language.name}) → "{meaning.translation.content}" ({meaning.translation.language.name})'
        entries.append(entry)

    entries_text = "\n".join(entries)
    return BATCH_MEANING_FREQUENCY_AND_TYPE_PROMPT.format(entries=entries_text)


def create_meaning_frequency_and_type_prompt(meaning):
    """
    Create a prompt to classify meaning frequency and phrase type for a single meaning.
    Uses dedicated single-item prompt for better reliability.

    Args:
        meaning: Meaning object with origin and translation

    Returns:
        str: Formatted prompt ready for API call
    """
    return MEANING_FREQUENCY_AND_TYPE_PROMPT.format(
        origin_word=meaning.origin.content,
        origin_language=meaning.origin.language.name,
        translation_word=meaning.translation.content,
        translation_language=meaning.translation.language.name,
    )


# Backward compatibility
def create_meaning_frequency_prompt(meaning):
    """Legacy function name for backward compatibility."""
    return create_meaning_frequency_and_type_prompt(meaning)


# Example usage with Anthropic API:
# from anthropic import Anthropic
# client = Anthropic(api_key=api_key)
# response = client.messages.create(
#     model="claude-sonnet-4-5-20250929",  # Latest model (September 2025)
#     max_tokens=20,  # Need space for "frequency,phrase_type"
#     temperature=0,  # Deterministic response
#     messages=[{
#         "role": "user",
#         "content": create_meaning_frequency_and_type_prompt(meaning)
#     }]
# )
# result = response.content[0].text.strip().lower()
# frequency, phrase_type = result.split(',')
