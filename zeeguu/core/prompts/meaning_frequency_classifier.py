"""
Prompt for classifying meaning frequency and phrase type using Anthropic API.
Designed to return only the classifications with minimal token usage.
"""

MEANING_FREQUENCY_AND_TYPE_PROMPT = """Classify this word/phrase meaning frequency and type.

Word/Phrase: {origin_word}
Language: {origin_language}
Translation: {translation_word}
Target language: {translation_language}

Frequency categories:
- unique: only meaning
- common: frequently used meaning (primary or very widespread usage)
- uncommon: infrequently used meaning (learners might encounter it occasionally, but it's not essential for basic communication)
- rare: rarely used meaning (specialized, archaic, or very context-specific)

Phrase type categories:
- single_word: individual word
- collocation: natural word combination
- idiom: idiomatic expression
- expression: common phrase/greeting
- arbitrary_multi_word: arbitrary multi-word selection (not a collocation, idiom, or expression)

Reply with ONLY: frequency,phrase_type (e.g., "common,single_word")"""


def create_meaning_frequency_and_type_prompt(meaning):
    """
    Create a prompt to classify meaning frequency and phrase type.
    
    Args:
        meaning: Meaning object with origin and translation
        
    Returns:
        str: Formatted prompt ready for API call
    """
    return MEANING_FREQUENCY_AND_TYPE_PROMPT.format(
        origin_word=meaning.origin.content,
        origin_language=meaning.origin.language.name,
        translation_word=meaning.translation.content,
        translation_language=meaning.translation.language.name
    )

# Backward compatibility
def create_meaning_frequency_prompt(meaning):
    """Legacy function name for backward compatibility."""
    return create_meaning_frequency_and_type_prompt(meaning)


# Example usage with Anthropic API:
# from anthropic import Anthropic
# client = Anthropic(api_key=api_key)
# response = client.messages.create(
#     model="claude-3-5-sonnet-20241022",  # Use current best model
#     max_tokens=20,  # Need space for "frequency,phrase_type"
#     temperature=0,  # Deterministic response
#     messages=[{
#         "role": "user",
#         "content": create_meaning_frequency_and_type_prompt(meaning)
#     }]
# )
# result = response.content[0].text.strip().lower()
# frequency, phrase_type = result.split(',')