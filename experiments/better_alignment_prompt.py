#!/usr/bin/env python3
"""
Test improved prompting for detecting particle verbs, idioms, and collocations.
"""

import anthropic
import os

def get_smart_alignment(text):
    """Get word alignment with explicit detection of multi-word expressions."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    prompt = f"""Analyze this Danish sentence and provide translation with word-level alignment.

Sentence: {text}

IMPORTANT: Detect and mark these special cases:
1. **Particle verbs** (e.g., "står...op" = "gets up") - mark as linked even if separated
2. **Idioms** (e.g., "regner skomagerdrenge" = "raining cats and dogs") - mark the whole phrase
3. **Collocations** (e.g., "stiller et spørgsmål" = "ask a question") - indicate if it's a fixed expression

Provide output as JSON:
{{
  "translation": "English translation",
  "tokens": [
    {{
      "source_word": "word",
      "source_pos": 1,
      "target_word": "word",
      "target_pos": 1,
      "type": "regular|particle_verb|idiom|collocation",
      "linked_positions": [1, 5]  // if this word is part of a multi-word expression, list all positions
    }}
  ],
  "multi_word_expressions": [
    {{
      "source_positions": [2, 5],
      "source_text": "står...op",
      "target_positions": [2, 3],
      "target_text": "gets up",
      "type": "particle_verb|idiom|collocation",
      "explanation": "why this is special"
    }}
  ]
}}

Skip punctuation in positions. Be thorough in detecting Danish particle verbs and idioms."""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=3096,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text

def test_sentence(text):
    """Test a sentence with improved prompting."""
    print(f"\n{'='*80}")
    print(f"Input: {text}")
    print('='*80)

    response = get_smart_alignment(text)
    print(response)

def main():
    test_cases = [
        # Separated particle verb
        "Hun står hver morgen op",

        # Separated particle verb with object
        "Han ringede sin mor op",

        # Collocation
        "De stiller et spørgsmål",

        # Famous idiom
        "Det regner skomagerdrenge",

        # Complex with multiple phenomena
        "Jeg giver aldrig op når det regner skomagerdrenge",

        # Another collocation
        "Hun tog bladet fra munden",
    ]

    for sentence in test_cases:
        test_sentence(sentence)
        print("\n")

if __name__ == "__main__":
    main()
