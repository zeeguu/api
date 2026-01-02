"""
Test LLM-based MWE detection with the problematic Danish example.

The issue: Stanza groups "kan se herunder" as one MWE, but:
- "kan se" = "can see" (modal + verb)
- "herunder" = "below/underneath" (adverb, NOT part of the verb phrase)

The LLM should recognize that "herunder" modifies WHERE you can see,
not WHAT "can see" means. It should NOT be grouped with "kan se".

Run with:
  ANTHROPIC_API_KEY="..." /Users/mircea/.venvs/z_env/bin/python -m tools._test_llm_mwe
"""

import os
import sys

# Add the api directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zeeguu.core.mwe.llm_strategy import LLMMWEStrategy
from zeeguu.core.mwe.strategies import GermanicStrategy


def test_danish_example():
    """Test the problematic Danish sentence."""

    # Simulated tokens for: "Du kan se herunder hvordan"
    # (You can see below how...)
    tokens = [
        {"text": "Du", "pos": "PRON", "dep": "nsubj", "head": 2, "lemma": "du"},
        {"text": "kan", "pos": "AUX", "dep": "aux", "head": 2, "lemma": "kunne"},
        {"text": "se", "pos": "VERB", "dep": "root", "head": 0, "lemma": "se"},
        {"text": "herunder", "pos": "ADV", "dep": "advmod", "head": 2, "lemma": "herunder"},
        {"text": "hvordan", "pos": "ADV", "dep": "advmod", "head": 2, "lemma": "hvordan"},
    ]

    print("=" * 70)
    print("TEST: Danish sentence 'Du kan se herunder hvordan'")
    print("=" * 70)
    print("\nTokens:")
    for i, t in enumerate(tokens):
        print(f"  {i}: {t['text']:12} pos={t['pos']:6} dep={t['dep']:8} head={t['head']}")

    # Test Stanza strategy
    print("\n" + "-" * 70)
    print("STANZA DETECTION (current behavior):")
    print("-" * 70)

    stanza_strategy = GermanicStrategy()
    stanza_groups = stanza_strategy.detect(tokens)

    if stanza_groups:
        for group in stanza_groups:
            head_idx = group["head_idx"]
            dep_indices = group["dependent_indices"]
            mwe_type = group["type"]

            all_indices = sorted([head_idx] + dep_indices)
            mwe_text = " ".join(tokens[i]["text"] for i in all_indices)

            print(f"\n  MWE detected: '{mwe_text}'")
            print(f"    Type: {mwe_type}")
            print(f"    Head: {tokens[head_idx]['text']} (idx {head_idx})")
            print(f"    Dependents: {[tokens[i]['text'] for i in dep_indices]} (idx {dep_indices})")

            # Analyze the issue
            if "herunder" in mwe_text:
                print(f"\n  ISSUE: 'herunder' is an adverb meaning 'below/underneath'")
                print(f"         It modifies WHERE you can see, not the verb itself.")
                print(f"         Stanza over-groups based on dependency, not semantics.")
    else:
        print("  No MWE detected")

    # Test LLM strategy
    print("\n" + "-" * 70)
    print("LLM DETECTION (high precision):")
    print("-" * 70)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n  Skipping LLM test - ANTHROPIC_API_KEY not set")
        return

    llm_strategy = LLMMWEStrategy("da")
    llm_groups = llm_strategy.detect(tokens)

    if llm_groups:
        for group in llm_groups:
            head_idx = group["head_idx"]
            dep_indices = group["dependent_indices"]
            mwe_type = group["type"]

            all_indices = sorted([head_idx] + dep_indices)
            mwe_text = " ".join(tokens[i]["text"] for i in all_indices)

            print(f"\n  MWE detected: '{mwe_text}'")
            print(f"    Type: {mwe_type}")
            print(f"    Head: {tokens[head_idx]['text']} (idx {head_idx})")
            print(f"    Dependents: {[tokens[i]['text'] for i in dep_indices]} (idx {dep_indices})")
    else:
        print("\n  No MWE detected (expected: LLM correctly identifies no fixed expression)")
        print("  'kan se' is a simple modal+verb, 'herunder' is just an adverb")

    # Summary
    print("\n" + "=" * 70)
    print("COMPARISON:")
    print("=" * 70)
    print(f"\n  Stanza found: {len(stanza_groups)} MWE group(s)")
    print(f"  LLM found:    {len(llm_groups)} MWE group(s)")

    if len(stanza_groups) > len(llm_groups):
        print("\n  -> LLM has HIGHER PRECISION (fewer false positives)")
        print("     Stanza over-detects based on syntactic patterns")
        print("     LLM understands semantic meaning")


def test_german_particle_verb():
    """Test a clear German particle verb (should be detected by both)."""

    # "Ich rufe dich morgen an" (I'll call you tomorrow)
    tokens = [
        {"text": "Ich", "pos": "PRON", "dep": "nsubj", "head": 2, "lemma": "ich"},
        {"text": "rufe", "pos": "VERB", "dep": "root", "head": 0, "lemma": "rufen"},
        {"text": "dich", "pos": "PRON", "dep": "obj", "head": 2, "lemma": "du"},
        {"text": "morgen", "pos": "ADV", "dep": "advmod", "head": 2, "lemma": "morgen"},
        {"text": "an", "pos": "ADP", "dep": "compound:prt", "head": 2, "lemma": "an"},
    ]

    print("\n\n" + "=" * 70)
    print("TEST: German sentence 'Ich rufe dich morgen an'")
    print("=" * 70)
    print("\nTokens:")
    for i, t in enumerate(tokens):
        print(f"  {i}: {t['text']:12} pos={t['pos']:6} dep={t['dep']:12} head={t['head']}")

    # Test Stanza
    print("\n" + "-" * 70)
    print("STANZA DETECTION:")
    print("-" * 70)

    stanza_strategy = GermanicStrategy()
    stanza_groups = stanza_strategy.detect(tokens)

    if stanza_groups:
        for group in stanza_groups:
            head_idx = group["head_idx"]
            dep_indices = group["dependent_indices"]
            all_indices = sorted([head_idx] + dep_indices)
            mwe_text = " ".join(tokens[i]["text"] for i in all_indices)
            print(f"\n  MWE detected: '{mwe_text}' = 'anrufen' (to call)")
            print(f"    This is a TRUE particle verb - correctly detected!")
    else:
        print("  No MWE detected (unexpected)")

    # Test LLM
    print("\n" + "-" * 70)
    print("LLM DETECTION:")
    print("-" * 70)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n  Skipping LLM test - ANTHROPIC_API_KEY not set")
        return

    llm_strategy = LLMMWEStrategy("de")
    llm_groups = llm_strategy.detect(tokens)

    if llm_groups:
        for group in llm_groups:
            head_idx = group["head_idx"]
            dep_indices = group["dependent_indices"]
            all_indices = sorted([head_idx] + dep_indices)
            mwe_text = " ".join(tokens[i]["text"] for i in all_indices)
            print(f"\n  MWE detected: '{mwe_text}'")
            print(f"    Both Stanza and LLM agree - this is a real MWE!")
    else:
        print("\n  No MWE detected (unexpected - 'anrufen' is a clear particle verb)")


if __name__ == "__main__":
    test_danish_example()
    test_german_particle_verb()

    print("\n\n" + "=" * 70)
    print("CONCLUSION:")
    print("=" * 70)
    print("""
For MWE detection:
- Stanza: High RECALL (finds most MWEs) but may over-detect
- LLM: High PRECISION (only real MWEs) but slower/costly
- Hybrid: Best of both - Stanza for candidates, LLM for validation

For translation context:
- Adjacent MWEs: Fuse and translate together
- Separated MWEs: Challenge! Options:
  1. Send full expression with ellipsis (current): "rufe...an"
  2. Send with context sentence (more accurate)
  3. Use MWE dictionary lookup (fastest)
""")
