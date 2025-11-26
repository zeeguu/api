# Bookmark Position Tracking

## Overview

Bookmarks store position information (`sentence_i`, `token_i`, `total_tokens`) to enable precise highlighting of words and multi-word phrases in exercises and the reader.

## Position Fields

- **`sentence_i`**: Sentence index where the word appears (0-indexed)
- **`token_i`**: Token index within the sentence (0-indexed) - for multi-word phrases, this is the FIRST token
- **`total_tokens`**: Number of tokens this bookmark spans (1 for single word, >1 for multi-word phrases)

## Problem History

### February 2025 Issue
- **What happened**: 1,203 bookmarks (66% of all affected) were created with NULL position data
- **Root cause**: Frontend refactoring on Feb 7, 2025 removed explicit position property copying, relying on `word.token` reference which was unreliable during word fusion
- **Impact**: Multi-word phrases like "ikke engang" would only highlight the last word ("engang") instead of the entire phrase
- **Time range**: February 13-28, 2025 (development/testing period)

### Fix History
- **Nov 11, 2025**: Added backend position validation on bookmark updates
- **Nov 11, 2025**: Created repair script to fix 1,818 affected bookmarks
- **Nov 11, 2025**: Added tests and database constraints to prevent recurrence

## Prevention Layers

### Layer 1: Backend Validation (Automatic)
**File**: `zeeguu/core/bookmark_operations/update_bookmark.py`

The `validate_and_update_position()` function automatically recalculates positions when bookmarks are updated:

```python
if context_or_word_changed(word_str, context_str, bookmark):
    error_response = validate_and_update_position(bookmark, word_str, context_str)
```

**Protection**: Even if frontend sends bad/missing position data, backend fixes it.

### Layer 2: Database Constraints (Preventive)
**Migration**: `tools/migrations/25-11-11--add-bookmark-position-constraints.sql`

Added NOT NULL constraints with defaults:
- `sentence_i INT NOT NULL DEFAULT 0`
- `token_i INT NOT NULL DEFAULT 0`
- `total_tokens INT NOT NULL DEFAULT 1`

**Protection**: Database rejects NULL values, preventing data corruption at the lowest level.

### Layer 3: Tests (Detection)
**File**: `zeeguu/api/test/test_bookmark_positions.py`

Comprehensive test suite covering:
- Single-word bookmark position tracking
- Multi-word bookmark position tracking
- Position recalculation on updates
- Prevention of NULL positions

**Protection**: Catches regressions before they reach production.

### Layer 4: Repair Tools (Recovery)
**File**: `tools/user_word_integrity/_fix_multiword_bookmark_positions.py`

Script to find and fix bookmarks with incorrect positions:

```bash
# Check for issues (dry-run)
python -m tools.user_word_integrity._fix_multiword_bookmark_positions

# Fix issues
python -m tools.user_word_integrity._fix_multiword_bookmark_positions --fix
```

**Protection**: Can fix historical data and recover from any future issues.

## Frontend Architecture

### Word Class (`js/web/src/reader/LinkedWordListClass.js`)

The `Word` class represents a word or multi-word phrase:

```javascript
class Word {
  this.word = "text content";
  this.token = /* reference to FIRST token */;  // ⚠️ See ABR 003
  this.total_tokens = 1;  // or >1 for multi-word
}
```

**IMPORTANT**: `this.token` refers to the FIRST token only, not all tokens. See [ABR 003](abr/003-frontend-word-class-naming-alignment.md) for proposed rename to `first_token`.

### Word Fusion

When users extend translations by fusing neighboring words:

```javascript
fuseWithPrevious(api) {
  this.word = this.prev.word + " " + this.word;
  this.token = this.prev.token;  // Takes position of FIRST token
  this.total_tokens += this.prev.total_tokens;
}
```

The fused word points to the position of the first token, ensuring correct highlighting.

### Position Calculation

Positions are sent to backend as relative to context:

```javascript
// InteractiveText.js:77-78
let wordSent_i = word.token.sent_i - cSent_i;    // Relative to context
let wordToken_i = word.token.token_i - cToken_i;
```

## Running the Repair Script

### Prerequisites
1. Activate virtual environment: `source ~/.venvs/z_env/bin/activate`

### Steps

1. **Check for issues** (dry-run):
```bash
python -m tools.user_word_integrity._fix_multiword_bookmark_positions
```

2. **Review output**: Lists all bookmarks with incorrect positions

3. **Fix issues**:
```bash
python -m tools.user_word_integrity._fix_multiword_bookmark_positions --fix
```

4. **Verify fix**: Run check again to ensure all issues resolved

### Options
- `--limit N`: Only check first N bookmarks (for testing)
- `--verbose`: Show detailed information about each incorrect bookmark
- `--fix`: Actually fix the positions (default is dry-run)

## Applying Database Constraints

### Prerequisites
1. **MUST** fix all existing NULL values first using the repair script
2. Verify no NULL values remain:
```sql
SELECT COUNT(*) FROM bookmark WHERE token_i IS NULL OR sentence_i IS NULL OR total_tokens IS NULL;
```

### Apply Migration
```bash
mysql -u zeeguu_test -pzeeguu_test zeeguu_test < tools/migrations/25-11-11--add-bookmark-position-constraints.sql
```

**WARNING**: Migration will FAIL if any NULL values exist. This is intentional - fix data first!

## Running Tests

```bash
# Run all position tracking tests
./run_tests.sh zeeguu/api/test/test_bookmark_positions.py

# Run specific test
./run_tests.sh zeeguu/api/test/test_bookmark_positions.py::test_multiword_bookmark_has_positions
```

## Monitoring

### Check for NULL Positions
```sql
SELECT
  COUNT(*) as null_positions,
  MIN(time) as first_occurrence,
  MAX(time) as last_occurrence
FROM bookmark
WHERE token_i IS NULL OR sentence_i IS NULL;
```

### Check Recent Bookmarks
```sql
-- Check bookmarks created in last 7 days
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN token_i IS NULL THEN 1 ELSE 0 END) as null_count
FROM bookmark
WHERE time >= DATE_SUB(NOW(), INTERVAL 7 DAY);
```

## Related Documentation

- [User/Bookmark/UserWord Architecture](USER_BOOKMARK_USERWORD_ARCHITECTURE.md)
- [ABR 002: UserWord Naming](abr/002-userword-naming-and-fit-for-study-placement.md)
- [ABR 003: Frontend Word Class Naming](abr/003-frontend-word-class-naming-alignment.md)
- [Integrity Checks README](../tools/user_word_integrity/README_INTEGRITY_CHECKS.md)
