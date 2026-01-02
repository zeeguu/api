"""
Test paragraph-level LLM alignment.

Instead of one sentence at a time, send a whole paragraph.
This reduces API calls and hides latency via prefetching.

Run with:
  ANTHROPIC_API_KEY="..." /Users/mircea/.venvs/z_env/bin/python -m tools._mwe_llm_paragraph
"""

import os
import time
import anthropic

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")

# A realistic Danish paragraph from an article
DANISH_PARAGRAPH = """
Han kom op med en god idé til projektet. Hun giver aldrig op, selv når det er svært.
Vi finder ud af det sammen. Han vil rejse til København i morgen.
"""

# German paragraph with various MWEs
GERMAN_PARAGRAPH = """
Er steht jeden Tag früh auf und ruft seine Mutter an. Sie gibt niemals auf.
Das ist mir Wurst, sagte er. Er wird morgen kommen.
"""

# French paragraph
FRENCH_PARAGRAPH = """
Il a mis le projet sur pied avec son équipe. Elle se rend compte de son erreur.
Il pleut des cordes aujourd'hui. Il va partir demain matin.
"""


def get_paragraph_alignment(client, paragraph, source_lang):
    """Get alignment for an entire paragraph at once."""

    prompt = f"""Translate this {source_lang} paragraph to English and show word-by-word alignment.

IMPORTANT: Group multi-word expressions together on a single line:
- Particle verbs (e.g., "steht auf" → "gets up")
- Idioms (e.g., "ist mir Wurst" → "I don't care")
- Grammatical constructions (e.g., "wird kommen" → "will come")

Format each alignment as: source → target
Separate sentences with a blank line.

Paragraph:
{paragraph}

Alignment:"""

    start = time.time()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    elapsed = time.time() - start

    return response.content[0].text, elapsed


def test_paragraph_alignment():
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    print("=" * 80)
    print("PARAGRAPH-LEVEL LLM ALIGNMENT TEST")
    print("=" * 80)

    tests = [
        ("Danish", DANISH_PARAGRAPH),
        ("German", GERMAN_PARAGRAPH),
        ("French", FRENCH_PARAGRAPH),
    ]

    total_time = 0

    for lang, paragraph in tests:
        print(f"\n\n{'#' * 80}")
        print(f"# {lang.upper()} PARAGRAPH")
        print(f"{'#' * 80}")

        print(f"\n[Source]\n{paragraph.strip()}")

        alignment, elapsed = get_paragraph_alignment(client, paragraph, lang)
        total_time += elapsed

        print(f"\n[Alignment] ({elapsed:.2f}s)")
        print(alignment)

    print(f"\n\n{'=' * 80}")
    print("TIMING SUMMARY")
    print(f"{'=' * 80}")
    print(f"\nTotal time for 3 paragraphs: {total_time:.2f}s")
    print(f"Average per paragraph: {total_time/3:.2f}s")

    # Estimate for typical article
    avg_paragraphs = 8
    print(f"\nFor a typical article ({avg_paragraphs} paragraphs):")
    print(f"  - Sequential: {avg_paragraphs * total_time/3:.1f}s")
    print(f"  - With prefetch (first paragraph): {total_time/3:.1f}s perceived latency")
    print(f"  - With read-ahead: ~0s perceived latency (all cached)")


if __name__ == "__main__":
    test_paragraph_alignment()
