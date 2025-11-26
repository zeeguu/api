#!/usr/bin/env python3
"""
Test script to measure Anthropic API translation speed for Danish sentences.
"""

import anthropic
import time
import os

def get_aligned_translation(text: str, source_lang: str = "Danish", target_lang: str = "English"):
    """
    Get word-aligned translation from Anthropic API.

    Returns the translation and the time taken.
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    prompt = f"""Translate this {source_lang} sentence to {target_lang} and provide word-level alignment.

Sentence: {text}

Please provide:
1. The translation
2. Word-level alignment showing which {source_lang} words correspond to which {target_lang} words

Format the alignment as a JSON array where each element shows the source word(s), target word(s), and their positions."""

    start_time = time.time()

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    end_time = time.time()
    elapsed_time = end_time - start_time

    response_text = message.content[0].text

    return response_text, elapsed_time, message.usage


def main():
    # Test sentences - including SEPARATED particle verbs, idioms, and collocations
    test_sentences = [
        # Basic example
        "Ultraforarbejdede fødevarer kan være skadelige for kroppen",

        # Separated particle verbs
        "Han ringede sin mor op",           # "ringede...op" separated by "sin mor" = "called...up"
        "Hun står hver morgen op",          # "står...op" separated by "hver morgen" = "gets up"
        "De tog deres jakker på",           # "tog...på" separated by "deres jakker" = "put...on"
        "Jeg slår computeren til",          # "slår...til" separated by "computeren" = "turn...on"
        "Vi satte det nye projekt i gang",  # "satte...i gang" separated by "det nye projekt" = "started"
        "Jeg giver aldrig op",              # "giver...op" separated by "aldrig" = "give...up"

        # Idioms (non-literal translations)
        "Det regner skomagerdrenge",        # Idiom: "It's raining shoemaker boys" = "It's raining cats and dogs"
        "Hun har en finger med i spillet",  # Idiom: "has a finger in the game" = "has a hand in it"
        "Det er ikke min kop te",           # Idiom: "not my cup of tea" = "not my cup of tea" (same!)
        "Han slog to fluer med et smæk",    # Idiom: "hit two flies with one swat" = "kill two birds with one stone"
        "Hun tog bladet fra munden",        # Idiom: "took the leaf from the mouth" = "spoke plainly"
        "Det er lige meget",                # Collocation: literally "it's equally much" = "it doesn't matter"

        # Collocations (fixed expressions)
        "Han har ret",                      # Collocation: "has right" = "is right/correct"
        "Vi tager en beslutning",           # Collocation: "take a decision" vs "make a decision"
        "Hun gjorde en indsats",            # Collocation: "did an effort" = "made an effort"
        "De stiller et spørgsmål",          # Collocation: "place a question" = "ask a question"
        "Jeg tager hensyn til det",         # Collocation: "take consideration to" = "take into account"

        # Control
        "Han bryder sit løfte",             # Regular verb - no particle
    ]

    for i, danish_sentence in enumerate(test_sentences, 1):
        print(f"\n{'='*80}")
        print(f"Test {i}/{len(test_sentences)}: '{danish_sentence}'")
        print("=" * 80)

        # Run the translation
        translation, elapsed_time, usage = get_aligned_translation(danish_sentence)

        print(f"\n⏱️  Response time: {elapsed_time:.2f} seconds")
        print(f"\n📊 Token usage:")
        print(f"   Input tokens: {usage.input_tokens}")
        print(f"   Output tokens: {usage.output_tokens}")
        print(f"\n💬 Response:\n")
        print(translation)

        # Calculate tokens per second
        tokens_per_sec = usage.output_tokens / elapsed_time
        print(f"\n📈 Generation speed: {tokens_per_sec:.1f} tokens/second")
        print("\n")


if __name__ == "__main__":
    main()
