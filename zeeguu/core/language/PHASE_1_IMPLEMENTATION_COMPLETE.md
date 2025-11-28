# Phase 1 Implementation Complete: CEFR Provenance Tracking

**Status**: ✅ Infrastructure Ready (Phase 1 of 4)
**Date**: 2025-10-14
**Goal**: Add tracking fields without changing behavior

---

## What Was Implemented

### 1. Database Schema Changes

**Migration File**: `tools/migrations/25-10-14--add_cefr_tracking_fields.sql`

Added 3 new columns to the `article` table:

| Column | Type | Purpose |
|--------|------|---------|
| `cefr_source` | ENUM | Tracks HOW difficulty was determined |
| `cefr_assessed_by_user_id` | INT (FK) | User ID if teacher manually set |
| `cloned_from_article_id` | INT (FK) | Article this was cloned from (teacher workflow) |

**cefr_source ENUM values**:
- `llm_assessed_deepseek` - LLM judged existing content (DeepSeek)
- `llm_assessed_anthropic` - LLM judged existing content (Anthropic)
- `llm_simplified` - LLM generated content AT target level
- `ml` - ML classifier (standard features)
- `ml_word_freq` - ML classifier with word frequency features
- `teacher` - Teacher manually set or confirmed
- `naive_fk` - Legacy FK→CEFR conversion
- `unknown` - Unknown origin (pre-tracking)

### 2. Data Backfill

The migration includes SQL to populate `cefr_source` for existing articles:

1. **Simplified articles** (`parent_article_id` IS NOT NULL) → `llm_simplified`
2. **LLM-assessed originals** (based on `simplification_ai_generator_id`) → `llm_assessed_deepseek` or `llm_assessed_anthropic`
3. **Unknown origins** (older articles) → `unknown`

### 3. Model Updates

**File**: `zeeguu/core/model/article.py`

Added new fields to the Article class:
```python
# CEFR provenance tracking
cefr_source = Column(Enum(...))
cefr_assessed_by_user_id = Column(Integer, ForeignKey("user.id"))

# Clone tracking
cloned_from_article_id = Column(Integer, ForeignKey("article.id"))

# Relationships
cefr_assessed_by = relationship("User", foreign_keys=[cefr_assessed_by_user_id])
cloned_from_article = relationship("Article", remote_side=[id], foreign_keys=[cloned_from_article_id])
```

### 4. Article Relationships Clarified

| Field | Points To | Meaning |
|-------|-----------|---------|
| `parent_article_id` | Original article | "This is an LLM-simplified version of that" |
| `cloned_from_article_id` | Source article | "This is a teacher clone/copy of that" |

These are **semantically different** and kept separate for clarity.

### 5. Indexes Added

For performance optimization:
- `idx_article_cefr_source` - Query by difficulty source
- `idx_article_cefr_assessed_by_user` - Find teacher assessments
- `idx_article_cloned_from` - Track clone relationships

---

## How to Deploy

### Step 1: Run Migration

```bash
# Connect to database
mysql -u username -p zeeguu_db

# Run migration
source tools/migrations/25-10-14--add_cefr_tracking_fields.sql

# Verify columns were added
DESCRIBE article;
```

### Step 2: Verify Data

```bash
source ~/.venvs/z_env/bin/activate && python
```

```python
from zeeguu.api.app import create_app
from zeeguu.core.model import Article, db

app = create_app()
with app.app_context():
    # Check that cefr_source was populated
    total = db.session.query(Article).filter(Article.cefr_level.isnot(None)).count()
    tracked = db.session.query(Article).filter(Article.cefr_source.isnot(None)).count()
    print(f"Articles with CEFR: {total}")
    print(f"Articles with source tracked: {tracked}")

    # Check distribution
    from sqlalchemy import func
    distribution = db.session.query(
        Article.cefr_source, func.count(Article.id)
    ).group_by(Article.cefr_source).all()
    print("\nDistribution:")
    for source, count in distribution:
        print(f"  {source}: {count}")
```

### Step 3: Update Application Code

The new fields are now available but **NOT YET USED**. Phase 1 is infrastructure only.

---

## What This Enables

### Immediate Benefits

1. **Historical tracking** - We can now see how every CEFR level was determined
2. **Analytics** - Compare accuracy of different methods over time
3. **Debugging** - Identify articles that need re-assessment
4. **Teacher feedback** - Track which articles teachers override
5. **Clone tracking** - Know which articles are teacher copies

### Foundation for Future Phases

- **Phase 2**: Use ML as primary for new articles
- **Phase 3**: Add word frequency enhancement
- **Phase 4**: Implement teacher confirmation workflow

---

## Example Queries Enabled

```python
# Find all ML-assessed articles
Article.query.filter(Article.cefr_source == 'ml').all()

# Find articles a teacher manually assessed
Article.query.filter(Article.cefr_assessed_by_user_id == teacher.id).all()

# Find all clones of a specific article
Article.query.filter(Article.cloned_from_article_id == original.id).all()

# Calculate drift for teacher edit
if article.cloned_from_article_id:
    original_content = article.cloned_from_article.get_content()
    current_content = article.get_content()
    drift_pct = calculate_edit_distance(original_content, current_content)
```

---

## Testing Checklist

- [x] Migration SQL is valid
- [x] Article model imports without errors
- [ ] Migration runs without errors on dev database
- [ ] All existing articles with CEFR have a `cefr_source`
- [ ] Foreign key constraints work (can't set invalid user_id)
- [ ] Indexes are created
- [ ] API still works (no breaking changes)

---

## Rollback Plan

If issues arise:

```sql
-- Remove indexes
DROP INDEX idx_article_cefr_source ON article;
DROP INDEX idx_article_cefr_assessed_by_user ON article;
DROP INDEX idx_article_cloned_from ON article;

-- Remove foreign key constraints
ALTER TABLE article DROP FOREIGN KEY fk_article_cefr_assessed_by_user;
ALTER TABLE article DROP FOREIGN KEY fk_article_cloned_from;

-- Remove columns
ALTER TABLE article DROP COLUMN cefr_source;
ALTER TABLE article DROP COLUMN cefr_assessed_by_user_id;
ALTER TABLE article DROP COLUMN cloned_from_article_id;
```

---

## Next Steps (Phase 2)

Once Phase 1 is deployed and verified:

1. **Update `Article.create_clone()`** to set `cloned_from_article_id`
2. **Update article creation code** to set `cefr_source`
3. **Modify crawlers** to use ML as primary instead of LLM
4. **Update simplification code** to set correct `cefr_source` values
5. **Train word-freq models** for all languages

See [RECOMMENDATION_ML_AS_PRIMARY.md](RECOMMENDATION_ML_AS_PRIMARY.md) for complete roadmap.

---

## Files Changed

1. **New**: `tools/migrations/25-10-14--add_cefr_tracking_fields.sql`
2. **Modified**: `zeeguu/core/model/article.py` (lines 105-145)

## Database Size Impact

- **3 new columns** per article
- **3 new indexes**
- Estimated storage increase: ~20 bytes per article
- For 100,000 articles: ~2MB increase

---

## Design Decisions

### Why NOT `cefr_assessed_at`?
- Timestamp adds complexity without clear use case
- Can use existing timestamps (published_time, etc.) if needed

### Why NOT `original_simplified_ancestor_id`?
- `parent_article_id` already tracks original for LLM-simplified
- `cloned_from_article_id` tracks source for teacher clones
- Can calculate drift on-the-fly when needed

### Why NOT `cumulative_edit_distance_pct`?
- Storing calculated values is premature optimization
- Can compute when showing suggestion dialog
- Avoids stale data issues

### Why separate `parent_article_id` and `cloned_from_article_id`?
- Semantically different: "LLM-simplified from" vs "teacher-cloned from"
- Clear intent in code
- Could rename `parent_article_id` later but keeping for now to minimize changes

---

## Questions?

See [IMPLEMENTATION_DECISIONS.md](IMPLEMENTATION_DECISIONS.md) for complete design rationale.
