#!/usr/bin/env python3
"""
Test Option 1: Send Stanza tokens to Anthropic for alignment.
This keeps existing DB schema while getting better alignments.
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

def get_alignment_with_stanza_tokens(text, stanza_tokens):
    """Get alignment from Anthropic using pre-tokenized Stanza tokens."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    token_list = [t['text'] for t in stanza_tokens]

    prompt = f"""Analyze this Danish sentence and provide translation with word-level alignment.

ORIGINAL TEXT: {text}

PRE-TOKENIZED TOKENS: {token_list}

CRITICAL REQUIREMENTS:
1. Use the EXACT token positions from the pre-tokenized list (1 to {len(token_list)})
2. DO NOT re-tokenize the text yourself
3. Token position 1 = "{token_list[0]}", position 2 = "{token_list[1]}", etc.
4. Detect particle verbs, idioms, and collocations using these exact positions
5. Mark punctuation tokens with type "punctuation"

Provide output as JSON:
{{
  "translation": "English translation",
  "tokens": [
    {{
      "source_word": "exact token from list",
      "source_pos": 1,  // MUST match position in pre-tokenized list
      "target_word": "translation",
      "target_pos": 1,
      "type": "regular|particle_verb|idiom|collocation|punctuation",
      "linked_positions": [1]  // positions that form a unit
    }}
  ],
  "multi_word_expressions": [
    {{
      "source_positions": [2, 5],  // positions from pre-tokenized list
      "source_text": "multi word expression",
      "target_positions": [2, 3],
      "target_text": "translation",
      "type": "particle_verb|idiom|collocation",
      "explanation": "why special"
    }}
  ]
}}

Remember: You MUST use the exact token positions from the pre-tokenized list provided above."""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text

def test_sentence(text):
    """Test a sentence with Stanza tokens sent to Anthropic."""
    print(f"\n{'='*80}")
    print(f"Original text: {text}")
    print('='*80)

    # Step 1: Tokenize with Stanza
    stanza_tokens = get_stanza_tokens(text)
    print(f"\nStanza tokens ({len(stanza_tokens)}):")
    for tok in stanza_tokens:
        tok_type = "PUNCT" if tok['text'] in '.,!?;:' else "WORD"
        print(f"  {tok['position']:2d}. '{tok['text']}' [{tok_type}]")

    # Step 2: Send to Anthropic with pre-tokenized positions
    print("\nSending to Anthropic with pre-tokenized positions...")
    response = get_alignment_with_stanza_tokens(text, stanza_tokens)

    print("\nAnthropic response:")
    print(response)

    # Step 3: Validate alignment
    print("\n" + "="*80)
    print("VALIDATION:")
    print("="*80)

    try:
        # Try to parse JSON from response
        json_str = response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()

        data = json.loads(json_str)

        # Check if all positions match Stanza
        anthropic_positions = [t['source_pos'] for t in data['tokens']]
        expected_positions = list(range(1, len(stanza_tokens) + 1))

        if anthropic_positions == expected_positions:
            print(f"✓ Position count matches! {len(anthropic_positions)} tokens")
            print("✓ All positions sequential and matching Stanza")
        else:
            print(f"✗ MISMATCH!")
            print(f"  Expected positions: {expected_positions}")
            print(f"  Anthropic positions: {anthropic_positions}")

        # Check for multi-word expressions
        if data.get('multi_word_expressions'):
            print(f"\n✓ Detected {len(data['multi_word_expressions'])} multi-word expressions:")
            for mwe in data['multi_word_expressions']:
                print(f"  - {mwe['type']}: {mwe['source_text']} (positions {mwe['source_positions']})")

    except Exception as e:
        print(f"⚠ Could not validate JSON: {e}")

def main():
    test_cases = [
        # Separated particle verb
        "Han ringede sin mor op, men hun svarede ikke",

        # Collocation
        "De stiller et spørgsmål",

        # Idiom
        "Det regner skomagerdrenge",

        # Complex case
        "Hun står op, hver morgen.",

        # Edge case: contractions/compounds
        "Ultraforarbejdede fødevarer kan være skadelige for kroppen",
    ]

    for sentence in test_cases:
        test_sentence(sentence)
        print("\n")

if __name__ == "__main__":
    main()
