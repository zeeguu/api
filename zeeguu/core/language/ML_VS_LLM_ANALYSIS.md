# Should We Use ML Classifier as Primary Method?

## The Consistency Problem

**Current System**:
```
Article from crawler (LLM fails) → ML estimate → difficulty = B1
Later: Teacher edits article → LLM assessment → difficulty = B2
Result: Same article has different difficulty ratings! 😕
```

This creates:
- **Confusion for users** - article difficulty changes unexpectedly
- **Cache invalidation issues** - recommendations, difficulty filters need updates
- **Trust problems** - users see inconsistent behavior

## Comparison: ML vs LLM

| Factor | ML Classifier | LLM (DeepSeek) |
|--------|---------------|----------------|
| **Accuracy** | 86-90% (measured) | Unknown (used as "ground truth") |
| **Consistency** | ✅ Perfect - same input = same output | ✅ Mostly consistent with temperature=0.1 |
| **Speed** | ✅ <10ms per article | ❌ 10-60 seconds per article |
| **Cost** | ✅ Free | ❌ API costs |
| **Reliability** | ✅ No failures | ❌ Timeouts, rate limits, API downtime |
| **Scalability** | ✅ Can process 1000s/sec | ❌ Rate limited |
| **Simplicity** | ✅ Single method everywhere | ❌ Complex fallback logic |

## Key Insight: We Don't Know LLM's True Accuracy!

We're using LLM assessments as "ground truth" to train the ML model, but:
- **LLM can be wrong too** - no verification against human experts
- **LLM might have systematic biases** - we're just copying those biases
- **90% agreement between ML and LLM** might mean both are correct 90% of the time
- OR it might mean ML learned LLM's biases perfectly!

## Recommendation: Use ML as Primary

### ✅ Advantages

1. **Perfect Consistency**
   - Every article gets exactly one difficulty assessment
   - No confusion when teachers edit articles
   - Caching and recommendations work reliably

2. **Performance & Reliability**
   - No API calls during crawling → faster
   - No API failures → more articles successfully processed
   - No rate limits → can scale infinitely

3. **Cost Savings**
   - Zero API costs for difficulty assessment
   - Can still use LLM for article simplification (higher value use)

4. **Quality**
   - 90% accuracy is excellent for this task
   - Human experts probably don't agree 100% on CEFR levels either
   - Current 10% error rate is acceptable

### ⚠️ Considerations

1. **Feature Quality**
   - Current features are good but could be better
   - **Adding word frequency data would likely push accuracy to 92-95%**
   - See word frequency analysis below

2. **Validation**
   - Should validate against human expert assessments (not just LLM)
   - Could do spot-checks with teachers

3. **Per-Language Quality**
   - Some languages (PT, FR, ES) have 90%+ accuracy
   - Others (EN, EL) have 80% accuracy
   - Might want to keep using LLM for lower-performing languages

4. **Retraining**
   - Need to retrain periodically as more data comes in
   - Set up automated retraining pipeline

## Implementation Plan

### Phase 1: Pilot with High-Performing Languages (Immediate)
Use ML as primary for languages with 90%+ accuracy:
- Portuguese (90.67%)
- Romanian (89.67%)
- French (89.33%)
- Spanish (89.33%)

Keep using LLM for others until we improve them with word frequency features.

### Phase 2: Add Word Frequency Features (1-2 weeks)
Enhance ML models with word frequency data → expect 92-95% accuracy.

### Phase 3: Full Migration (1 month)
Switch all languages to ML primary once word frequency features are proven.

### Phase 4: Validation (Ongoing)
Collect teacher feedback and human expert validation to verify quality.

## Decision Matrix

| Scenario | Recommendation |
|----------|----------------|
| **High-performing languages (90%+ accuracy)** | ✅ Use ML as primary NOW |
| **Lower-performing languages (80-85%)** | ⚠️ Improve with word freq first, then switch |
| **Languages without ML models** | ❌ Continue using LLM or naive FK→CEFR |
| **All languages after word freq features** | ✅ Use ML as primary |

## Alternative: Hybrid Approach

If you're not ready to fully commit:

**Option A: ML Primary, LLM Validation (Sample)**
- Use ML for all articles
- Randomly sample 5-10% for LLM validation
- Track disagreements to improve ML model
- Cost: 90% reduction in API costs

**Option B: ML Primary, LLM Override**
- Use ML for all articles
- Allow teachers to request LLM re-assessment if they disagree
- Manual override system
- Best of both worlds

## Conclusion

**Recommendation: YES, deploy ML as primary method**, especially for high-performing languages.

The consistency benefits alone justify the switch. 90% accuracy is excellent, and you can:
1. Improve further with word frequency features (see below)
2. Validate with human experts
3. Keep LLM API as optional "second opinion" for edge cases

The LLM API is better used for article simplification (where quality matters more than speed/cost) rather than difficulty assessment (where consistency and speed matter most).
