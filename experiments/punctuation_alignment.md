# Experiment Report: Punctuation Alignment

**Date:** 2025-11-26
**Experiment:** Test approaches for handling punctuation in token alignment

## Problem

Stanza tokenizes punctuation as separate tokens, but Anthropic initially skipped punctuation in alignment, causing position mismatches.

**Example:**
- Stanza: `["Han", "ringede", "sin", "mor", "op", ",", "men", "hun", "svarede", "ikke"]` (10 tokens)
- Anthropic: `[1, 2, 3, 4, 5, 6, 7, 8, 9]` (9 positions - comma skipped)
- **Mismatch!** Position 6 means different things

## Tested Approaches

### Approach 1: Ask Anthropic to Include Punctuation

Modified prompt to explicitly request:
```
"Include ALL tokens including punctuation marks (commas, periods, etc.) in positions"
```

### Approach 2: Post-hoc Alignment

Map Anthropic word positions to Stanza tokens by:
1. Filter Stanza tokens to word-only
2. Map Anthropic positions to word indices
3. Convert back to absolute Stanza positions

## Results

### ✅ Approach 1: SUCCESS

When explicitly asked to include punctuation, Anthropic:

**Example:** "Han ringede sin mor op, men hun svarede ikke"

```json
{
  "tokens": [
    {"source_word": "Han", "source_pos": 1},
    {"source_word": "ringede", "source_pos": 2},
    {"source_word": "sin", "source_pos": 3},
    {"source_word": "mor", "source_pos": 4},
    {"source_word": "op", "source_pos": 5},
    {"source_word": ",", "source_pos": 6, "type": "punctuation"},
    {"source_word": "men", "source_pos": 7},
    {"source_word": "hun", "source_pos": 8},
    {"source_word": "svarede", "source_pos": 9},
    {"source_word": "ikke", "source_pos": 10}
  ]
}
```

**Stanza tokens:** 10
**Anthropic positions:** 10
**✓ Perfect match!**

Additionally:
- Punctuation marked with `"type": "punctuation"`
- Still detects particle verbs correctly (ringede...op at positions [2, 5])
- All other linguistic features preserved

### ✓ Approach 2: Also Feasible

Mapping algorithm works:
```
Anthropic pos 1 → Stanza word #1 → Stanza absolute pos 1
Anthropic pos 2 → Stanza word #2 → Stanza absolute pos 2
...
Anthropic pos 6 → Stanza word #6 → Stanza absolute pos 7 (skips comma at pos 6)
```

But requires:
- Post-processing logic
- Filtering punctuation from Stanza
- Mapping layer

## Test Results Summary

| Test Sentence | Stanza Tokens | Anthropic (Approach 1) | Match? |
|--------------|---------------|------------------------|--------|
| "Han ringede sin mor op, men hun svarede ikke" | 10 | 10 | ✅ |
| "Hun står op, hver morgen." | 7 | 7 | ✅ |
| "De stiller et spørgsmål; jeg svarer." | 8 | 8 | ✅ |

## Conclusions

### Recommendation: Use Approach 1

**Reasons:**
1. ✅ Simpler - no post-processing needed
2. ✅ Perfect alignment with Stanza
3. ✅ Punctuation properly typed
4. ✅ No mapping errors
5. ✅ Cleaner architecture

**Implementation:**
Just add to prompt:
```
"Include ALL tokens including punctuation marks (commas, periods, etc.) and number positions sequentially."
```

### Remaining Challenge

**Both Stanza and Anthropic are ML models** - no guarantee they'll tokenize identically in all edge cases:
- Contractions: "I'll", "won't"
- Special constructions: French "est-ce que"
- Compound words
- Future model updates

**This leads to Option 1 in next experiment:** Send Stanza tokens to Anthropic to ensure consistency.

## Next Steps

- [ ] Test sending pre-tokenized Stanza tokens to Anthropic (see stanza_tokens_to_anthropic.py)
- [ ] Evaluate if Approach 1 is sufficient for production
- [ ] Edge case testing: contractions, compounds, multiple languages
