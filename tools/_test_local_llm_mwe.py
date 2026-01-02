"""
Test local LLMs (via Ollama) for MWE detection + translation.

Run with:
  python -m tools._test_local_llm_mwe
"""

import json
import time
import requests

# Test paragraphs in different languages
TEST_CASES = [
    {
        "lang": "Danish",
        "text": "Men lysten til at blive vaccineret har ikke været overvældende. Spækhuggere jager laks i havet ved Canada.",
        "expected_mwes": ["at blive vaccineret", "har ikke været"],
    },
    {
        "lang": "German",
        "text": "Ich rufe dich morgen an. Er steht jeden Tag früh auf.",
        "expected_mwes": ["rufe...an", "steht...auf"],
    },
    {
        "lang": "Dutch",
        "text": "Hij staat elke dag vroeg op. Zij geeft nooit op.",
        "expected_mwes": ["staat...op", "geeft...op"],
    },
]

PROMPT_TEMPLATE = """Analyze this {lang} paragraph for language learners.

1. Identify multi-word expressions (MWEs) that should be learned as units:
   - Particle verbs (separable verbs like "give up", "stand up")
   - Idioms (non-literal phrases)
   - Fixed expressions

2. Provide word-by-word translations to English.

Paragraph: "{text}"

Return JSON only (no markdown, no explanation):
{{
  "mwes": [
    {{"text": "the mwe text", "translation": "english translation", "type": "particle_verb|idiom|fixed"}}
  ],
  "words": [
    {{"word": "original", "translation": "english"}}
  ]
}}

JSON:"""


def call_ollama(model: str, prompt: str, timeout: int = 120) -> tuple[str, float]:
    """Call Ollama API and return response + time taken."""
    start = time.time()

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temp for consistent output
                    "num_predict": 1000,
                }
            },
            timeout=timeout
        )
        response.raise_for_status()
        result = response.json()
        elapsed = time.time() - start
        return result.get("response", ""), elapsed
    except Exception as e:
        elapsed = time.time() - start
        return f"ERROR: {e}", elapsed


def parse_response(response: str) -> dict:
    """Try to parse JSON from response."""
    # Clean up response
    response = response.strip()

    # Remove markdown code blocks if present
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0]
    elif "```" in response:
        response = response.split("```")[1].split("```")[0]

    # Find JSON object
    start = response.find("{")
    end = response.rfind("}") + 1
    if start >= 0 and end > start:
        response = response[start:end]

    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        return {"error": str(e), "raw": response[:500]}


def test_model(model: str, test_case: dict) -> dict:
    """Test a model with a specific test case."""
    prompt = PROMPT_TEMPLATE.format(lang=test_case["lang"], text=test_case["text"])

    print(f"\n  Calling {model}...", end=" ", flush=True)
    response, elapsed = call_ollama(model, prompt)
    print(f"({elapsed:.1f}s)")

    parsed = parse_response(response)

    return {
        "model": model,
        "elapsed": elapsed,
        "parsed": parsed,
        "raw_response": response[:1000] if "error" in parsed else None,
    }


def main():
    # Models to test (from user's list, ordered by capability)
    models = [
        "gemma3:12b",      # Largest, should be best
        "llama3:latest",   # Good general purpose
        "deepseek-r1:latest",  # Reasoning model
        "gemma3:latest",   # Smaller gemma
    ]

    print("=" * 70)
    print("LOCAL LLM MWE DETECTION + TRANSLATION TEST")
    print("=" * 70)

    # Check which models are available
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        available = [m["name"] for m in response.json().get("models", [])]
        print(f"\nAvailable models: {available}")
    except:
        print("\nWarning: Could not check available models")
        available = models

    results = []

    for test_case in TEST_CASES[:1]:  # Start with just Danish
        print(f"\n{'=' * 70}")
        print(f"TEST: {test_case['lang']}")
        print(f"Text: {test_case['text'][:80]}...")
        print(f"Expected MWEs: {test_case['expected_mwes']}")
        print("=" * 70)

        for model in models:
            if not any(model.split(":")[0] in m for m in available):
                print(f"\n  Skipping {model} (not available)")
                continue

            result = test_model(model, test_case)
            results.append(result)

            parsed = result["parsed"]
            if "error" in parsed:
                print(f"  ERROR: {parsed['error']}")
                if result["raw_response"]:
                    print(f"  Raw: {result['raw_response'][:200]}...")
            else:
                print(f"  MWEs found:")
                for mwe in parsed.get("mwes", []):
                    print(f"    - {mwe.get('text', '?')} → {mwe.get('translation', '?')}")

                words = parsed.get("words", [])
                print(f"  Word translations: {len(words)} words")
                for w in words[:5]:
                    print(f"    - {w.get('word', '?')} → {w.get('translation', '?')}")
                if len(words) > 5:
                    print(f"    ... and {len(words) - 5} more")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for r in results:
        status = "✓" if "error" not in r["parsed"] else "✗"
        mwe_count = len(r["parsed"].get("mwes", [])) if "error" not in r["parsed"] else 0
        print(f"{status} {r['model']:20} | {r['elapsed']:5.1f}s | {mwe_count} MWEs")


if __name__ == "__main__":
    main()
