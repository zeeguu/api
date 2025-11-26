#!/usr/bin/env python3
"""
Test two approaches for handling punctuation in alignment:
1. Ask Anthropic to include punctuation in tokenization
2. Do post-hoc alignment between Anthropic positions and Stanza tokens
"""

import stanza
import anthropic
import os
import json

# Initialize Stanza for Danish
print("Loading Stanza Danish model...")
nlp = stanza.Pipeline('da', processors='tokenize', verbose=False)

def get_stanza_tokens(text):
    """Get tokens from Stanza (including punctuation)."""
    doc = nlp(text)
    tokens = []
    for sentence in doc.sentences:
        for token in sentence.tokens:
            tokens.append({
                'text': token.text,
                'start_char': token.start_char,
                'end_char': token.end_char,
                'position': len(tokens) + 1
            })
    return tokens

def approach1_ask_anthropic_for_punctuation(text):
    """Approach 1: Ask Anthropic to include punctuation in alignment."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    prompt = f"""Analyze this Danish sentence and provide translation with word-level alignment.

Sentence: {text}

IMPORTANT REQUIREMENTS:
1. Include ALL tokens including punctuation marks (commas, periods, etc.)
2. Detect particle verbs, idioms, and collocations
3. Number positions sequentially INCLUDING punctuation

Example: "Han kom, men gik" should have 5 positions: Han(1), kom(2), ,(3), men(4), gik(5)

Provide output as JSON:
{{
  "translation": "English translation",
  "tokens": [
    {{
      "source_word": "word or punctuation",
      "source_pos": 1,
      "target_word": "word or punctuation",
      "target_pos": 1,
      "type": "regular|particle_verb|idiom|collocation|punctuation",
      "linked_positions": [1]
    }}
  ],
  "multi_word_expressions": [
    {{
      "source_positions": [2, 5],
      "source_text": "multi word expression",
      "target_positions": [2, 3],
      "target_text": "translation",
      "type": "particle_verb|idiom|collocation",
      "explanation": "why special"
    }}
  ]
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=3096,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text

def approach2_post_alignment(text, anthropic_response):
    """Approach 2: Align Anthropic positions (no punct) to Stanza tokens (with punct)."""
    stanza_tokens = get_stanza_tokens(text)

    # Parse Anthropic response to get word positions
    # This is a simplified version - you'd need proper JSON parsing
    print("\nStanza tokens (with punctuation):")
    for tok in stanza_tokens:
        tok_type = "PUNCT" if tok['text'] in '.,!?;:' else "WORD"
        print(f"  {tok['position']:2d}. '{tok['text']}' [{tok_type}]")

    print("\nAlignment strategy:")
    print("  - Map Anthropic word positions to Stanza word tokens (skip punct)")
    print("  - Keep punctuation tokens but mark them as non-alignable")

    # Create mapping
    stanza_words_only = [t for t in stanza_tokens if t['text'] not in '.,!?;:']

    print(f"\nStanza word-only count: {len(stanza_words_only)}")
    print("Word-only tokens:")
    for tok in stanza_words_only:
        print(f"  Stanza pos {tok['position']} = '{tok['text']}'")

    return stanza_tokens, stanza_words_only

def test_both_approaches(text):
    """Test both approaches and compare."""
    print(f"\n{'='*80}")
    print(f"Testing: {text}")
    print('='*80)

    # Approach 1: Ask Anthropic to include punctuation
    print("\n--- APPROACH 1: Ask Anthropic to include punctuation ---")
    response1 = approach1_ask_anthropic_for_punctuation(text)
    print(response1)

    # Approach 2: Post-hoc alignment
    print("\n--- APPROACH 2: Post-hoc alignment (Anthropic words → Stanza tokens) ---")
    # For approach 2, we'd use the response without punctuation from earlier
    stanza_tokens, stanza_words = approach2_post_alignment(text, None)

    print("\nMapping strategy:")
    print("  Anthropic position 1 → Stanza word-only position 1 → Stanza absolute position")
    for i, word_tok in enumerate(stanza_words, 1):
        print(f"  Anthropic pos {i} → Stanza word #{i} → Stanza absolute pos {word_tok['position']}")

def main():
    test_cases = [
        "Han ringede sin mor op, men hun svarede ikke",
        "Hun står op, hver morgen.",
        "De stiller et spørgsmål; jeg svarer.",
    ]

    for sentence in test_cases:
        test_both_approaches(sentence)
        print("\n")

if __name__ == "__main__":
    main()
