#!/usr/bin/env python3
"""
Compare Stanza tokenization vs Anthropic's word-level alignment.
This tests if Anthropic's alignment positions map to Stanza tokens.
"""

import stanza
import anthropic
import os
import re

# Initialize Stanza for Danish
print("Loading Stanza Danish model...")
nlp = stanza.Pipeline('da', processors='tokenize', verbose=False)

def get_stanza_tokens(text):
    """Get tokens from Stanza."""
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

def get_anthropic_alignment(text):
    """Get word alignment from Anthropic."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    prompt = f"""For this Danish sentence, provide:
1. The English translation
2. Word-by-word alignment

Sentence: {text}

Format as JSON with this structure:
{{
  "translation": "the English translation",
  "alignments": [
    {{"source_word": "word", "source_pos": 1, "target_word": "word", "target_pos": 1}},
    ...
  ]
}}

Be precise about word positions (1-indexed) and handle multi-word expressions appropriately."""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text

def compare_tokenizations(text):
    """Compare Stanza tokens vs Anthropic alignment."""
    print(f"\n{'='*80}")
    print(f"Input: {text}")
    print('='*80)

    # Get Stanza tokens
    stanza_tokens = get_stanza_tokens(text)
    print(f"\nStanza tokens ({len(stanza_tokens)}):")
    for tok in stanza_tokens:
        print(f"  {tok['position']:2d}. '{tok['text']}' (chars {tok['start_char']}-{tok['end_char']})")

    # Get Anthropic alignment
    print("\nGetting Anthropic alignment...")
    anthropic_response = get_anthropic_alignment(text)
    print(f"\nAnthropic response:\n{anthropic_response}")

    # Try to extract alignment positions
    print("\n" + "="*80)
    print("ANALYSIS:")
    print("="*80)

    # Extract source positions from response
    source_positions = re.findall(r'"source_pos":\s*(\d+)', anthropic_response)
    if source_positions:
        print(f"\nAnthropic word positions: {', '.join(source_positions)}")
        print(f"Stanza token count: {len(stanza_tokens)}")

        if len(source_positions) == len(stanza_tokens):
            print("✓ Position counts match!")
        else:
            print(f"✗ MISMATCH: Anthropic has {len(source_positions)} positions, Stanza has {len(stanza_tokens)} tokens")

    # Check for multi-word expressions
    multi_word = re.findall(r'"source_pos":\s*"?(\d+-\d+)', anthropic_response)
    if multi_word:
        print(f"\n⚠ Multi-word expressions detected: {multi_word}")
        print("  These will need special handling in the bookmark model")

def main():
    test_sentences = [
        # Simple sentence
        "Hun står hver morgen op",

        # Collocation
        "De stiller et spørgsmål",

        # Idiom
        "Det regner skomagerdrenge",

        # With punctuation
        "Han ringede sin mor op, men hun svarede ikke",

        # With contractions/compounds
        "Ultraforarbejdede fødevarer kan være skadelige for kroppen",
    ]

    for sentence in test_sentences:
        compare_tokenizations(sentence)

if __name__ == "__main__":
    main()
