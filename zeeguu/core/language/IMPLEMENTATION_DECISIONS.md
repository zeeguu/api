# ML Difficulty Estimation - Implementation Decisions & Findings

**Date**: October 14, 2025
**Status**: Active Development
**Context**: Discussions on deploying ML as primary difficulty estimation method

---

## 📋 Table of Contents

1. [Original Problem](#original-problem)
2. [Evaluation Results](#evaluation-results)
3. [Word Frequency Enhancement](#word-frequency-enhancement)
4. [Critical Discovery: Simplified Articles](#critical-discovery-simplified-articles)
5. [Teacher Workflow Challenges](#teacher-workflow-challenges)
6. [Final Design Decisions](#final-design-decisions)
7. [Implementation Roadmap](#implementation-roadmap)

---

## Original Problem

### The Consistency Issue

**Problem**: Articles get different difficulty ratings depending on when/how they're assessed:

```
Scenario:
1. Article crawled (LLM fails) → ML estimates B1
2. Later: Teacher edits article → LLM reassesses → Now B2
3. Result: Same article has TWO different ratings! 😕
```

**User Impact**:
- Confusion - why did difficulty change?
- Cache invalidation - recommendations need recalculation
- Trust issues - system appears unreliable

**Root Cause**: Using LLM as primary with ML as fallback creates inconsistency.

### Proposed Solution

**Use ML as PRIMARY method for all articles** (not just fallback):
- ✅ Perfect consistency - same input = same output
- ✅ Fast (<10ms vs 10-60s)
- ✅ Zero cost (no API calls)
- ✅ Never fails (no timeouts/rate limits)
- ✅ 86-90% accuracy already excellent

**Key Insight**: We don't actually know if LLM is more accurate - we just assumed it! Human experts probably don't agree 100% on CEFR levels either.

---

## Evaluation Results

### Methodology

Evaluated 3 methods on 300 original articles per language (11 languages, 3,300 total):

1. **LLM API (DeepSeek)** - Used as "ground truth" for training
2. **ML Classifier (Random Forest)** - Trained on LLM assessments
3. **Naive FK→CEFR** - Old fallback based only on Flesch-Kincaid

**Key Principle**: Overestimating (saying harder) is BETTER than underestimating (saying easier). We don't want to demoralize users with content that's too hard.

### Results Summary

| Metric | Naive FK→CEFR | ML Classifier | Improvement |
|--------|---------------|---------------|-------------|
| **Accuracy** | 23.9% | 86.3% | **+62.4 pp** |
| **Cost** (2x underest. penalty) | 1.85 | 0.28 | **-84.9%** |
| **Underestimation Rate** | 62.1% | 9.7% | **-84.4%** |

### Per-Language Results (Top Performers)

| Language | ML Accuracy | Underest. Reduction |
|----------|-------------|---------------------|
| Portuguese | 90.67% | 178 → 17 (-90.4%) |
| Romanian | 89.67% | 208 → 25 (-88.0%) |
| French | 89.33% | 288 → 21 (-92.7%) |
| Spanish | 89.33% | 257 → 20 (-92.2%) |

**Conclusion**: ML classifier is SIGNIFICANTLY better than naive FK→CEFR across all 11 languages.

See [EVALUATION_SUMMARY.md](EVALUATION_SUMMARY.md) for complete results.

---

## Word Frequency Enhancement

### Hypothesis

**Question**: Would word frequency (rank) data improve accuracy?

**Answer**: YES! Word frequency is one of the strongest predictors of vocabulary difficulty.

### Why Word Frequency Matters

```
Easy (A2):  "The cat sat on the mat"
            → All words in top 500

Hard (C1):  "The ubiquitous feline perched precariously..."
            → "ubiquitous" = rank 15,000
            → "precariously" = rank 12,000
```

Vocabulary difficulty is a MAJOR component of CEFR assessment.

### Features Added

Using existing `wordstats` library and `Phrase.rank` data:

1. **avg_word_rank** - Lower = easier
2. **median_word_rank** - Robust measure
3. **pct_top_1000/5000/10000** - Vocabulary coverage
4. **pct_rare_words** (>10,000 rank) - Difficulty spikes
5. **max_word_rank** - Hardest word in text
6. **word_rank_90th_percentile** - Overall difficulty without outliers

### Portuguese Test Results

**Standard ML Model:**
- Accuracy: 87.60%
- Underestimates: 40 (8.0%)
- Cost: 0.22

**Word-Freq Enhanced Model:**
- Accuracy: **90.60%** ✅
- Underestimates: **32 (6.4%)** ✅
- Cost: **0.17** ✅

**Improvements:**
- **+3.0 percentage points** accuracy (as predicted!)
- **-20% underestimation** reduction
- **-24.5% cost** improvement

**Conclusion**: Word frequency features provide real predictive value. Training accuracy was 75% due to simplified articles (see below), but on original articles the model achieves 90.60%.

---

## Critical Discovery: Simplified Articles

### The Problem

Training with word frequency showed **75% accuracy** initially, but **90.60% on original articles**. Investigation revealed:

**Simplified A1 articles are NOT truly A1 by vocabulary:**

```
Simplified A1: "Líder do PS... primeiro-ministro..."
- Grammar: Simple ✓
- Sentences: Short ✓
- Words: "primeiro-ministro" (Prime Minister) NOT in A1 vocabulary ✗
- 65% words in top 1000 (improved from 41% in original)
- BUT still 14% rare words (>10k rank)
```

### Why This Happens

**Domain vocabulary cannot be simplified away:**
- "Timor-Leste" is "Timor-Leste" at all CEFR levels
- "direitos humanos" (human rights) - no simpler equivalent
- "primeiro-ministro" (prime minister) - fundamental concept

### Two CEFR Philosophies

**1. Vocabulary-based (Word Frequency Model thinks this):**
- A1 = only top 1000 words
- Problem: Can't discuss interesting topics!

**2. Grammar-based (LLM thinks this, pedagogically correct):**
- A1 = simple grammar + short sentences + necessary domain terms
- Example: "China tem problemas com mosquitos"
  - Grammar: A1 ✓
  - Sentences: Short ✓
  - Words: "China", "mosquitos" not A1, but that's OK!

**Pedagogical Consensus**: Approach #2 is correct. A1 learners CAN read about complex topics if structure is simple.

### Impact on Word Frequency Models

**Problem**: Word-freq model sees domain vocabulary and thinks "This is B1!"

**Example from Analysis**:
```
Article labeled: A1 (LLM simplified)
Word frequency stats:
  - 66% in top 1000 (good!)
  - 14% rare words >10k (model sees this as B1 signal)
  - FK difficulty: 19 (actually simple!)
  - Avg sentence: 15 words (short!)

Word-freq model predicts: B1
Correct answer: A1 (pedagogical choice to include domain terms)
```

**Solution**: Treat simplified articles differently (see Final Design).

---

## Teacher Workflow Challenges

### The Edit-Save-Edit Problem

**Scenario**: Teacher workflow creates complexity:

```
1. Teacher finds: Simplified A1 article (ID: 12345)
2. Teacher saves: Creates COPY (NEW ID: 99999)
3. Teacher edits: Changes a few words
4. System must: Re-evaluate difficulty
5. Problem: ML might say B1! (sees domain terms)
6. Worse: Even LLM might give different answer (non-deterministic)
```

### The Drift Problem

**Scenario A: Anchor to Previous (naive)**
```
Original A1 → Edit 1 (4% change) → Save as A1 ✓
              Edit 2 (4% more) → Save as A1 ✓
              Edit 3 (4% more) → Save as A1 ✓
              ...
              Edit 10 (4% more) → Save as A1 ✓

Total drift: 40%! But system thinks "each edit was small"
```

**Scenario B: Anchor to Original (correct)**
```
Original A1 (ID: 12345)
→ Edit 1: 4% from original → Save as A1 ✓
→ Edit 2: 7% total from original → Save as A1 ✓
→ Edit 3: 12% total from original → Save as A1 ✓
→ Edit 4: 22% total from original → Re-assess! ⚠️
```

**Solution**: Track original simplified ancestor and cumulative drift.

### Initial Complex Solutions Considered

We initially considered:
- "Locking" difficulty levels
- Pedagogical override flags
- Soft locks vs hard locks
- Weighted re-assessment with edit distance

**Final Realization**: These were all too complex!

---

## Final Design Decisions

### Core Principles

1. **System suggests, teacher decides** - NEVER auto-update
2. **Single source of truth** - `article.cefr_level` is the answer
3. **Track provenance** - Know HOW difficulty was determined
4. **No locks needed** - System never touches levels without permission

### Database Schema

```python
class Article(db.Model):
    # Existing
    cefr_level = db.Column(db.String(2))  # 'A1', 'A2', etc.

    # NEW: Track how difficulty was determined
    cefr_source = db.Column(
        db.Enum('llm', 'ml', 'ml_word_freq', 'teacher', 'naive_fk', 'unknown')
    )
    cefr_assessed_at = db.Column(db.DateTime)
    cefr_assessed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    # NEW: Track editing lineage
    original_simplified_ancestor_id = db.Column(
        db.Integer, db.ForeignKey('article.id')
    )
    immediate_parent_id = db.Column(db.Integer, db.ForeignKey('article.id'))
    cumulative_edit_distance_pct = db.Column(db.Float, default=0.0)
```

### Source Enum Values

```python
class CEFRSource(enum.Enum):
    # LLM-based assessments
    LLM_ASSESSED_DEEPSEEK = 'llm_assessed_deepseek'    # DeepSeek assessed original article
    LLM_ASSESSED_ANTHROPIC = 'llm_assessed_anthropic'  # Anthropic assessed original article
    LLM_SIMPLIFIED = 'llm_simplified'                  # Simplified by LLM (inherits assessment)

    # ML-based assessments
    ML = 'ml'                                          # ML without word freq (legacy)
    ML_WORD_FREQ = 'ml_word_freq'                      # ML with word freq (current best)

    # Human and fallback
    TEACHER = 'teacher'                                # Teacher manually set/overrode
    NAIVE_FK = 'naive_fk'                              # Old FK formula
    UNKNOWN = 'unknown'                                # Migrated data, unclear source
```

**Key Distinctions**:
- `llm_assessed_*` → LLM analyzed existing article and determined its level
- `llm_simplified` → Article was generated by LLM at a target level (pedagogical curation)
- Provider matters → DeepSeek vs Anthropic may have different accuracy/biases

### When Each Source is Used

```python
# Example 1: Article crawled from RSS
article = create_from_rss(url)
article.cefr_level = ml_assess_with_word_freq(article)
article.cefr_source = 'ml_word_freq'
article.ai_model = None

# Example 2: Teacher uploads article for assessment
article = create_from_teacher_upload(content)
assessment_result = deepseek_api.assess(article)
article.cefr_level = assessment_result.level  # e.g., "B2"
article.cefr_source = 'llm_assessed_deepseek'
article.ai_model = 'deepseek-chat'

# Example 3: Article simplified to A1 by DeepSeek
original = Article.query.get(12345)  # B2 article
simplified = simplify_article(original, target_level='A1', model='deepseek')
simplified.cefr_level = 'A1'  # Target level
simplified.cefr_source = 'llm_simplified'  # Generated, not assessed
simplified.ai_model = 'deepseek-chat'
simplified.parent_article_id = original.id

# Example 4: Article simplified to A1 by Anthropic
simplified = simplify_article(original, target_level='A1', model='claude')
simplified.cefr_level = 'A1'
simplified.cefr_source = 'llm_simplified'  # Note: same source!
simplified.ai_model = 'claude-3-5-sonnet'  # But different model
simplified.parent_article_id = original.id

# Example 5: Teacher overrides ML assessment
article.cefr_level = 'B1'  # ML said B2, teacher says B1
article.cefr_source = 'teacher'
article.cefr_assessed_by_user_id = teacher.id
article.ai_model = None  # Not AI-derived
```

**Important**: For `llm_simplified`, the `ai_model` field tells you WHICH LLM did the simplification, but `cefr_source` is the same regardless of provider.

### Quick Reference: Source vs ai_model

| Scenario | cefr_source | ai_model | cefr_level |
|----------|-------------|----------|------------|
| RSS crawl (new) | `ml_word_freq` | `NULL` | ML-predicted |
| Teacher upload + DeepSeek assess | `llm_assessed_deepseek` | `deepseek-chat` | LLM-assessed |
| Teacher upload + Anthropic assess | `llm_assessed_anthropic` | `claude-3-5-sonnet` | LLM-assessed |
| DeepSeek simplified to A1 | `llm_simplified` | `deepseek-chat` | `A1` (target) |
| Anthropic simplified to A2 | `llm_simplified` | `claude-3-5-sonnet` | `A2` (target) |
| Teacher overrides | `teacher` | `NULL` | Teacher choice |
| Old article (unknown) | `unknown` | varies | Unknown |

**Rule of Thumb**:
- `cefr_source` → How was the level determined?
- `ai_model` → Which AI (if any) was involved?

### Workflow: Teacher Saves Article

```python
def save_teacher_article(article, new_content, teacher):
    # 1. Calculate cumulative drift from original ancestor
    if article.original_simplified_ancestor_id:
        ancestor = Article.query.get(article.original_simplified_ancestor_id)
        drift_pct = calculate_edit_distance(ancestor.content, new_content)
    else:
        drift_pct = calculate_edit_distance(article.content, new_content)

    # 2. Get ML suggestion (NEVER auto-apply!)
    suggested_level = ml_assess_with_word_freq(article)

    # 3. Show to teacher in UI
    return {
        'current_level': article.cefr_level,
        'suggested_level': suggested_level,
        'drift_pct': drift_pct,
        'needs_review': (drift_pct > 10 or suggested_level != article.cefr_level)
    }
```

```python
def finalize_teacher_save(article, teacher_chosen_level, teacher):
    # Teacher decides - that's final!
    article.cefr_level = teacher_chosen_level
    article.cefr_assessed_at = datetime.now()

    # Track how it was determined
    if teacher_chosen_level == ml_assess_with_word_freq(article):
        article.cefr_source = 'ml_word_freq'  # Accepted suggestion
        article.cefr_assessed_by_user_id = None
    else:
        article.cefr_source = 'teacher'  # Override
        article.cefr_assessed_by_user_id = teacher.id
```

### Special Handling: Simplified Articles

**Decision**: Simplified articles should NOT be re-assessed with word frequency models.

**Rationale**:
- LLM made pedagogical choice: "A1 despite domain vocabulary"
- Word-freq model doesn't understand this nuance
- Teacher experience: A1 should stay A1

**Implementation**:
```python
def assess_article_difficulty(article):
    # Check if this is pedagogically curated content
    if article.cefr_source == 'llm_simplified':
        # This was GENERATED at a specific level, not assessed
        # The LLM chose to keep domain terms for pedagogical reasons
        # Word-freq model would misclassify this
        if article.cefr_source == 'teacher':
            # Teacher has overridden - trust them
            return article.cefr_level
        else:
            # Keep the LLM's pedagogical choice
            # Don't re-assess - it was curated, not estimated
            return article.cefr_level

    # Derived from simplified article (teacher edited)
    if article.original_simplified_ancestor_id:
        # This is derived from pedagogically curated content
        # Suggest re-assessment but bias toward grammar-based features
        return assess_without_word_freq(article)

    # Original articles: use word-freq model
    return ml_assess_with_word_freq(article)
```

**Key Insight**: `llm_simplified` articles are fundamentally different:
- `llm_assessed_deepseek`: "DeepSeek thinks this existing article is B2"
- `llm_simplified`: "DeepSeek generated this to BE A1 (pedagogically curated)"

The second case is a **target**, not an **assessment**. Don't second-guess it with ML.

### Why No "Lock" Field Needed

**Original concern**: What if system keeps changing teacher's choice?

**Solution**: System NEVER auto-updates. It only:
1. Suggests in UI
2. Waits for teacher confirmation
3. Saves teacher's choice with `cefr_source = 'teacher'`

**No lock needed because**:
- System respects `cefr_level` as single source of truth
- `cefr_source` tracks provenance
- Teacher override is permanent until teacher changes it

### UI Example

```
┌──────────────────────────────────────────────────┐
│ Save Article                                      │
├──────────────────────────────────────────────────┤
│ Current difficulty: A1                            │
│ System suggests: A2 (based on ML)                │
│ Changes from original: 15%                       │
│                                                   │
│ What level should this be?                       │
│ ( ) A2 - Accept system suggestion                │
│ (•) A1 - Keep current level                      │
│ ( ) Other: [  ▼]                                 │
│                                                   │
│ [Save]  [Cancel]                                 │
└──────────────────────────────────────────────────┘
```

### Benefits of Tracking Source

**1. Trust Signals**
```python
if article.cefr_source == 'teacher':
    display = f"{article.cefr_level} ✓ (verified by teacher)"
else:
    display = f"{article.cefr_level} (ML assessed)"
```

**2. Analytics**
```sql
-- How often do teachers override?
SELECT
    cefr_source,
    COUNT(*) as count
FROM article
WHERE cefr_assessed_at > DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY cefr_source;
```

**3. Re-evaluation Targeting**
```python
# Find articles to re-assess with new model
old_articles = Article.query.filter(
    Article.cefr_source.in_(['naive_fk', 'llm']),
    Article.cefr_source != 'teacher'  # Don't override teacher
).all()
```

**4. Debugging**
```
Why is this article B1?
→ cefr_source = 'ml_word_freq'
→ cefr_assessed_at = 2025-10-14
→ Means: ML model assessed it, not teacher override
```

---

## Implementation Roadmap

### Phase 1: Infrastructure (Week 1)

**Goal**: Add tracking fields, no behavior changes yet

1. Add database columns:
   ```sql
   ALTER TABLE article
   ADD COLUMN cefr_source ENUM(
       'llm_assessed_deepseek',
       'llm_assessed_anthropic',
       'llm_simplified',
       'ml',
       'ml_word_freq',
       'teacher',
       'naive_fk',
       'unknown'
   ) DEFAULT 'unknown',
   ADD COLUMN cefr_assessed_at DATETIME,
   ADD COLUMN cefr_assessed_by_user_id INT,
   ADD COLUMN original_simplified_ancestor_id INT,
   ADD COLUMN cumulative_edit_distance_pct FLOAT,
   ADD FOREIGN KEY (cefr_assessed_by_user_id) REFERENCES user(id);
   ```

2. Backfill existing data:
   ```sql
   UPDATE article
   SET cefr_source = CASE
       -- Simplified articles (generated by LLM)
       WHEN parent_article_id IS NOT NULL THEN 'llm_simplified'

       -- Original articles with LLM assessment
       -- Note: Need to check ai_model column to determine provider
       WHEN cefr_level IS NOT NULL AND ai_model LIKE '%deepseek%'
           THEN 'llm_assessed_deepseek'
       WHEN cefr_level IS NOT NULL AND ai_model LIKE '%claude%'
           THEN 'llm_assessed_anthropic'
       WHEN cefr_level IS NOT NULL
           THEN 'llm_assessed_deepseek'  -- Default assumption for old data

       -- No assessment
       ELSE 'unknown'
   END;
   ```

3. Update Article model with new fields

**No functional changes yet** - just tracking infrastructure.

### Phase 2: Word Frequency Models (Weeks 2-3)

**Goal**: Train and validate word-freq models for all languages

1. Train all languages:
   ```bash
   source ~/.venvs/z_env/bin/activate && \
   python -m tools.train_cefr_with_word_freq --all
   ```

2. Evaluate improvements:
   ```bash
   python -m tools.compare_ml_with_vs_without_word_freq --all
   ```

3. Expected outcome: 92-95% accuracy for top languages

### Phase 3: Teacher Workflow (Week 4)

**Goal**: Implement suggest-but-don't-auto-update for teacher edits

1. Update save_teacher_article() to:
   - Calculate drift from ancestor
   - Get ML suggestion
   - Return both to UI (don't auto-apply)

2. Create UI for teacher confirmation:
   - Show current vs suggested
   - Radio buttons for choice
   - Save with appropriate `cefr_source`

3. Test teacher workflow thoroughly

### Phase 4: Deploy ML as Primary (Week 5)

**Goal**: Switch to ML for all NEW articles

1. For newly crawled articles:
   ```python
   article.cefr_level = ml_assess_with_word_freq(article)
   article.cefr_source = 'ml_word_freq'
   ```

2. Keep LLM for simplified articles (during simplification)

3. Monitor for issues:
   - Teacher override rate
   - User complaints
   - Accuracy spot-checks

### Phase 5: Validation (Ongoing)

**Goal**: Ensure quality and improve

1. Human expert validation (sample 100 articles)
2. Track teacher override patterns
3. Retrain quarterly as data accumulates
4. A/B test if needed

---

## Key Decisions Summary

| Decision | Rationale |
|----------|-----------|
| **Use ML as primary** | 90% accuracy, perfect consistency, no API costs |
| **Add word frequency** | +3pp accuracy, -20% underestimation |
| **Never auto-update** | Teacher must confirm all changes |
| **Track source** | Know how difficulty was determined |
| **No lock field** | System never touches levels without permission |
| **Special case simplified** | Don't use word-freq on pedagogically curated content |
| **Track ancestor** | Prevent drift through multiple edits |

---

## Files Reference

- **[EVALUATION_SUMMARY.md](EVALUATION_SUMMARY.md)** - Full evaluation results
- **[RECOMMENDATION_ML_AS_PRIMARY.md](RECOMMENDATION_ML_AS_PRIMARY.md)** - Deployment roadmap
- **[README.md](README.md)** - Main documentation index
- **[ml_cefr_classifier_with_word_freq.py](ml_cefr_classifier_with_word_freq.py)** - Enhanced model code
- **[tools/train_cefr_with_word_freq.py](/tools/train_cefr_with_word_freq.py)** - Training script

---

## Open Questions

1. **Backfill old articles?** - Should we re-assess all articles with new ML model, or only new ones?

2. **Teacher notification?** - Should teachers be notified when ML suggests a different level than current?

3. **Confidence scores?** - Should ML models return confidence scores (e.g., "90% confident this is B1")?

4. **Multi-model ensemble?** - Should we combine ML + LLM predictions for even higher accuracy?

5. **Language-specific tuning?** - Some languages (EN, EL) have lower accuracy. Train separate models or adjust features?

---

## Next Steps

1. ✅ Portuguese word-freq model trained and validated (+3pp accuracy)
2. ⏳ Implement database schema changes (Phase 1)
3. ⏳ Train word-freq models for all languages (Phase 2)
4. ⏳ Update teacher save workflow (Phase 3)
5. ⏳ Deploy ML as primary for new articles (Phase 4)

---

**Last Updated**: October 14, 2025
**Authors**: Implementation discussion with Mircea
**Status**: Ready for Phase 1 implementation
