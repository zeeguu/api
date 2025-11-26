# Experiment Report: Better Alignment Prompting

**Date:** 2025-11-26
**Experiment:** Test if improved prompting can detect particle verbs, idioms, and collocations

## Objective

Determine if explicit prompting can make Anthropic Claude detect and properly align:
1. Separated particle verbs (e.g., "står...op" = "gets up")
2. Idioms (e.g., "regner skomagerdrenge" = "raining cats and dogs")
3. Collocations (e.g., "stiller et spørgsmål" = "ask a question")

## Method

Enhanced the prompt to explicitly request:
- Detection of particle verbs with `linked_positions`
- Marking of idioms and collocations
- A `multi_word_expressions` section with explanations
- Type classification: `regular|particle_verb|idiom|collocation`

## Results

### ✅ SUCCESS - All phenomena detected correctly

#### Particle Verbs (Separated)

**Example:** "Hun står hver morgen op" (She gets up every morning)

```json
{
  "source_positions": [2, 5],
  "source_text": "står...op",
  "target_positions": [2, 3],
  "target_text": "gets up",
  "type": "particle_verb",
  "explanation": "Danish separable particle verb 'at stå op' meaning 'to get up/wake up'.
                  The verb 'står' and particle 'op' are separated by other sentence elements."
}
```

✓ Correctly identified positions [2, 5] as linked
✓ Both tokens marked with `"type": "particle_verb"`
✓ Explanation provided

#### Idioms

**Example:** "Det regner skomagerdrenge" (It's raining cats and dogs)

```json
{
  "source_positions": [2, 3],
  "source_text": "regner skomagerdrenge",
  "target_positions": [2, 3, 4, 5],
  "target_text": "raining cats and dogs",
  "type": "idiom"
}
```

✓ Correctly translated to English idiom (not literal "shoemaker boys")
✓ Marked as idiom
✓ Showed non-1:1 mapping (2 Danish words → 4 English words)

#### Collocations

**Example:** "De stiller et spørgsmål" (They ask a question)

```json
{
  "source_positions": [2, 3, 4],
  "source_text": "stiller et spørgsmål",
  "target_positions": [2, 3, 4],
  "target_text": "ask a question",
  "type": "collocation",
  "explanation": "Fixed verbal collocation. 'Stiller' literally means 'put/place',
                  but 'stille et spørgsmål' is the standard way to express 'ask a question'."
}
```

✓ All 3 tokens marked as part of collocation
✓ Explanation of literal vs. idiomatic meaning

#### Complex Example

**Example:** "Jeg giver aldrig op når det regner skomagerdrenge"
(I never give up when it's raining cats and dogs)

Detected BOTH:
1. Particle verb: "giver...op" [positions 2, 4]
2. Idiom: "regner skomagerdrenge" [positions 7, 8]

## Conclusions

### What Works

✅ Explicit prompting successfully detects multi-word expressions
✅ Separated particle verbs are correctly identified and linked
✅ Idioms are translated idiomatically, not literally
✅ Collocations are marked with pedagogical explanations
✅ `linked_positions` provides exact token groupings

### Data Structure Quality

The returned JSON provides:
- **Token-level metadata:** Type classification for each token
- **Expression-level metadata:** Grouped positions and explanations
- **Pedagogical value:** Explanations of why expressions are special

### Implications for Zeeguu

This rich alignment data enables:
1. **Smart highlighting:** When user clicks position 2 or 5 in "står...op", highlight both
2. **Expression learning:** Create one bookmark for the whole expression, not separate words
3. **Pedagogical notes:** Show learners why "stiller et spørgsmål" is special
4. **Better translations:** Context-aware, idiomatic translations instead of word-by-word

## Next Steps

- [ ] Test with Stanza tokenization (see REPORT_punctuation_alignment.md)
- [ ] Design DB schema for storing multi-word expressions
- [ ] Prototype UI for highlighting linked tokens
- [ ] Cost analysis for batch article translation
