#!/usr/bin/env python3
"""
Test combining multiple article processing tasks in a single Anthropic call:
1. CEFR level assessment
2. Topic classification
3. Disturbing content detection
4. Word-level alignment with translation
5. Summary generation

This shows how to consolidate API calls for efficiency.
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

def process_article_all_in_one(title, content, language_code):
    """
    Process article with a single Anthropic API call.

    Returns all processing results:
    - CEFR level assessment
    - Topic classification
    - Disturbing content detection
    - Word-level alignment for translation
    - Multi-word expressions (particle verbs, idioms, collocations)
    - Summary
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Tokenize with Stanza first
    full_text = f"{title}\n\n{content}"
    stanza_tokens = get_stanza_tokens(full_text)
    token_list = [t['text'] for t in stanza_tokens]

    prompt = f"""Analyze this {language_code} article and provide comprehensive analysis in a SINGLE response.

ARTICLE TITLE: {title}

ARTICLE CONTENT: {content}

PRE-TOKENIZED TOKENS (use these exact positions): {token_list}

Please provide ALL of the following in JSON format:

1. **CEFR Level Assessment**: Assess difficulty (A1, A2, B1, B2, C1, C2)
2. **Topic Classification**: Main topic/category
3. **Content Classification**: Is this disturbing news, advertorial, or incomplete/paywalled?
4. **Summary**: Brief summary (2-3 sentences)
5. **Word-Level Alignment**: Translate and align using the EXACT pre-tokenized positions
   - Detect particle verbs, idioms, and collocations
   - Mark punctuation
   - Provide linked_positions for multi-word expressions

Output format:
{{
  "cefr_level": "B2",
  "topic": "Politics|Technology|Health|etc.",
  "is_disturbing": false,
  "is_advertorial": false,
  "is_incomplete": false,
  "summary": "Brief article summary...",

  "translation": {{
    "english_text": "Full English translation...",
    "tokens": [
      {{
        "source_word": "exact token from list",
        "source_pos": 1,
        "target_word": "translation",
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
  }}
}}

CRITICAL: Use the EXACT token positions (1 to {len(token_list)}) from the pre-tokenized list above."""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text

def test_combined_processing():
    """Test combined processing on a sample Danish article."""

    title = "Danmark mangler satellitter i Arktis"
    content = """Danmark er den eneste arktiske nation uden egne satellitter, hvilket gør landet afhængigt af andre. En ny rapport advarer om at dette gør Danmark sårbart i krisesituationer. Allerede er der politisk enighed og penge afsat til at etablere satellitkapacitet for bedre overvågning i Arktis."""

    print(f"\n{'='*80}")
    print(f"Processing article: {title}")
    print('='*80)
    print(f"\nContent preview: {content[:200]}...")

    print("\nTokenizing with Stanza...")
    tokens = get_stanza_tokens(f"{title}\n\n{content}")
    print(f"Token count: {len(tokens)}")

    print("\nSending combined request to Anthropic...")
    print("Requesting:")
    print("  ✓ CEFR level assessment")
    print("  ✓ Topic classification")
    print("  ✓ Content flags (disturbing/advertorial/incomplete)")
    print("  ✓ Summary generation")
    print("  ✓ Full translation with alignment")
    print("  ✓ Multi-word expression detection")

    result = process_article_all_in_one(title, content, "Danish")

    print("\n" + "="*80)
    print("RESULT:")
    print("="*80)
    print(result)

    # Try to parse and validate
    print("\n" + "="*80)
    print("VALIDATION:")
    print("="*80)

    try:
        json_str = result
        if "```json" in result:
            json_str = result.split("```json")[1].split("```")[0].strip()

        data = json.loads(json_str)

        print(f"✓ CEFR Level: {data.get('cefr_level')}")
        print(f"✓ Topic: {data.get('topic')}")
        print(f"✓ Disturbing: {data.get('is_disturbing')}")
        print(f"✓ Advertorial: {data.get('is_advertorial')}")
        print(f"✓ Incomplete: {data.get('is_incomplete')}")
        print(f"✓ Summary: {data.get('summary', '')[:100]}...")

        translation = data.get('translation', {})
        if translation:
            token_count = len(translation.get('tokens', []))
            mwe_count = len(translation.get('multi_word_expressions', []))
            print(f"✓ Aligned tokens: {token_count}")
            print(f"✓ Multi-word expressions: {mwe_count}")

            if translation.get('multi_word_expressions'):
                print("\n  Multi-word expressions found:")
                for mwe in translation['multi_word_expressions']:
                    print(f"    - {mwe['type']}: {mwe['source_text']} → {mwe['target_text']}")

        print("\n✅ ALL TASKS COMPLETED IN SINGLE API CALL")

    except Exception as e:
        print(f"⚠ Could not parse JSON: {e}")

def main():
    test_combined_processing()

if __name__ == "__main__":
    main()
