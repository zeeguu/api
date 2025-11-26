# Combined Article Processing Experiment Summary

**Date**: 2025-11-26
**Experiment**: Testing consolidated LLM calls for article processing during crawling

## Goal

Explore whether we can combine multiple article processing tasks into fewer LLM calls to:
1. Reduce API costs
2. Simplify crawling pipeline
3. Improve processing speed

## What We Tested

### Original Idea: Everything in One Call
Combine all tasks in a single LLM call:
- CEFR level assessment
- Topic classification
- Content flags (disturbing/advertorial/paywall)
- Full article translation with word-level alignment
- Multi-word expression detection
- Summary generation

**Test Results**:
- Processing time: 97.9 seconds for 1000-word article
- Output: 26,513 chars (~6,600 tokens)
- Cost: ~$0.10 per article = **$100 per 1000 articles**
- Issue: JSON parsing errors with very long outputs

## Cost Analysis

### Approach Comparison (per 1000 articles)

| Approach | Cost | During Crawl | When User Opens |
|----------|------|--------------|-----------------|
| **Full translation upfront** | $100 | Everything | Nothing |
| **Metadata only** | $27 | CEFR, topic, flags | Full translation |
| **Abstract translation** | $16 | CEFR, topic, flags, summary translation | Full translation |
| **Current system** | $50 | Simplification (3 versions) + classification | On-demand translation |

### Recommended Approach: Current System + Summary Translation

**During Crawling** (~$57 per 1000 articles):

1. **Call 1: Simplification + Classification** (keep current system)
   - Cost: ~$0.05 per article
   - Returns: A2/B1/B2 simplified versions + content flags

2. **Call 2: Translate Summary** (NEW - add this)
   - Cost: ~$0.007 per article
   - Tokenize summary with Stanza
   - Translate with word alignment
   - Returns: English summary + token alignment + multi-word expressions

**When User Opens Article**:
- Translate full article on-demand
- Only pay for articles actually read (~20%)

**Total Monthly Cost** (assuming 1000 articles crawled, 200 opened):
- Crawling: $57
- On-demand translations: ~$17
- **Total: ~$74/month**

vs. current system without summary translation: ~$67/month
**Additional cost: $7/month for translated summaries in article browser**

## Key Findings

### ✓ Benefits of Summary Translation
1. **Better UX**: Users see English summaries when browsing articles
2. **Context for learning**: Translated summary helps users decide what to read
3. **Low cost**: Only $7 extra per month for 1000 articles
4. **Simple implementation**: Just add one small LLM call after simplification

### ✗ Problems with Full Translation During Crawl
1. **Expensive**: $100/1000 articles, most never read
2. **Slow**: 97 seconds per article
3. **Fragile**: Large JSON outputs cause parsing errors
4. **Wasteful**: Translating articles nobody opens

### ✓ Why Current System (Simplification) Must Stay
- Users need simplified versions to read (core product feature)
- Can't defer simplification to on-demand (defeats purpose)
- Already generates 3 versions per article
- Cost is justified because simplification is the product

## Recommendations

### Implement Summary Translation (Low Risk, High Value)

**Add to `article_downloader.py` after simplification**:

```python
# After simplify_and_classify() completes
if new_article.summary:
    # Tokenize summary
    summary_tokens = tokenize_with_stanza(new_article.summary)

    # Translate summary with alignment
    summary_translation = translate_summary_with_alignment(
        new_article.summary,
        summary_tokens,
        new_article.language.code
    )

    # Save to database
    new_article.summary_en = summary_translation['english_text']
    new_article.summary_alignment = summary_translation['alignment']
```

**Benefits**:
- Article browser shows English summaries
- Users can decide what to read before clicking
- Token alignment available for summary preview
- Only $7/month extra for 1000 articles

### Don't Implement Full Translation During Crawl

**Reasons**:
- Too expensive ($100/1000 vs $57/1000)
- Most translations never used (80% articles not opened)
- Creates fragile large JSON parsing
- On-demand translation works fine

### Output Format: Skip JSON, Use Structured Text

For summary translation, use simple format instead of JSON:

```
ENGLISH_TEXT:
Ernest Ryu used ChatGPT to solve a 42-year-old mathematical problem...

MULTI_WORD_EXPRESSIONS:
1. 42 år gammelt (42-year-old) [positions: 5,6,7]
2. kom op med (came up with) [positions: 23,24,25]
...
```

**Why**:
- Easier to parse with regex
- No JSON formatting errors
- Slightly fewer output tokens
- More robust for production

## Implementation Plan

1. ✅ Keep current simplification system (`simplify_and_classify`)
2. ✅ Add summary translation call (new function)
3. ✅ Use structured text format (not JSON)
4. ✅ Store `summary_en` in Article model
5. ✅ Update article browser UI to show translated summaries

**Estimated effort**: 2-3 hours
**Estimated cost impact**: +$7/month per 1000 articles
**User benefit**: High (better article browsing experience)

## Files Created

- `/tmp/cost_analysis.md` - Full cost comparison
- `/tmp/abstract_translation_analysis.md` - Summary translation approach
- `/tmp/test_long_article.py` - Test script with long article
- `experiments/combined_article_processing.py` - Original experiment code

## Conclusion

**Best approach**: Add lightweight summary translation to current system for $7/month extra. Don't do full translation during crawl - too expensive and wasteful. Current on-demand translation for full articles is the right approach.

The experiment confirmed that:
1. Combining everything in one call is expensive and fragile
2. Summary translation is cheap and valuable
3. Current simplification system should be kept
4. On-demand full translation is cost-efficient
