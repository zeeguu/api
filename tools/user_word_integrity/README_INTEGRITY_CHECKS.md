# Data Integrity Checks

## Overview

The UserWord integrity check system ensures data consistency through multiple layers:

1. **Write-time validation** - SQLAlchemy event listeners prevent corruption at write time
2. **Periodic checks** - Daily cron job detects and fixes issues
3. **Manual tools** - Scripts for on-demand checking and repair

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Write-Time Prevention (user_word.py:430-462)     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  SQLAlchemy event listeners catch issues BEFORE commit      │
│  Raises ValueError if preferred_bookmark_id is invalid      │
│  → Prevents data corruption from happening                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Daily Automated Checks (cron job)                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  Run: python -m tools.user_word_integrity._daily_integrity_check --fix          │
│  Schedule: Daily at 3 AM                                    │
│  → Detects and auto-fixes issues that slip through          │
└─────────────────────────────────────────────────────────────┘
─────────────────────┐
│  Layer 2: Daily Automated Checks (cron job)                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  Run: python -m tools.user_word_integrity._daily_integrity_check --fix          │
│  Schedule: Daily at 3 AM                                    │
│  → Detects and auto-fixes issues that slip through          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Manual Tools (on-demand)                         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  Run: python -m tools.user_word_integrity._check_and_fix_data_integrity --fix  │
│  → For emergency repairs or investigation                   │
└─────────────────────────────────────────────────────────────┘
```

## Scripts

### 1. Daily Integrity Check (Recommended for Cron)

**File:** `tools/user_word_integrity/_daily_user_word_integrity_check.py`

**Purpose:** Lightweight daily check with auto-fix capability

**Usage:**

```bash
# Check only (report issues)
python -m tools.user_word_integrity._daily_user_word_integrity_check

# Check and fix
python -m tools.user_word_integrity._daily_user_word_integrity_check --fix

# Skip slow orphan check
python -m tools.user_word_integrity._daily_user_word_integrity_check --fix --skip-orphaned
```

**Exit codes:**

- `0` - Success (no issues or all fixed)
- `1` - Issues found but not fixed (report mode)

**Cron setup:**

```bash
# Add to crontab (crontab -e)
# Run daily at 3 AM, auto-fix issues, log output
0 3 * * * cd /path/to/zeeguu/api && source ~/.venvs/z_env/bin/activate && python -m tools.user_word_integrity._daily_user_word_integrity_check --fix --skip-orphaned >> /var/log/zeeguu_integrity.log 2>&1
```

### 2. Full Integrity Check (Manual Investigation)

**File:** `tools/user_word_integrity/_check_and_fix_user_word_integrity.py`

**Purpose:** Comprehensive check with detailed reporting

**Usage:**

```bash
# Dry-run: report all issues
python -m tools.user_word_integrity._check_and_fix_user_word_integrity

# Fix all issues including orphans
python -m tools.user_word_integrity._check_and_fix_user_word_integrity --fix

# Skip orphan check (faster)
python -m tools.user_word_integrity._check_and_fix_user_word_integrity --fix --skip-orphaned
```

**What it checks:**

1. UserWords with wrong `preferred_bookmark_id` (points to bookmark belonging to different UserWord)
2. UserWords with NULL `preferred_bookmark_id` despite having bookmarks
3. Orphaned UserWords (no bookmarks at all)

### 3. Cleanup Orphaned UserWords (Focused Tool)

**File:** `tools/user_word_integrity/_cleanup_orphaned_user_words.py`

**Purpose:** Dedicated tool for finding and cleaning up orphaned UserWords with better UX

**Usage:**

```bash
# Find all orphaned UserWords (dry-run)
python -m tools.user_word_integrity._cleanup_orphaned_user_words

# Verbose output (show details)
python -m tools.user_word_integrity._cleanup_orphaned_user_words --verbose

# For specific user
python -m tools.user_word_integrity._cleanup_orphaned_user_words --user-email i@mir.lu

# Actually delete (with confirmation prompt)
python -m tools.user_word_integrity._cleanup_orphaned_user_words --delete
```

**Features:**

- Per-user filtering (by email or ID)
- Verbose mode showing word details
- Interactive confirmation before deletion
- Groups results by user
- Deletes associated schedules automatically

## Issues Detected

### Issue 1: Wrong preferred_bookmark_id

**Problem:**

```sql
UserWord 123: preferred_bookmark_id = 456
  → But Bookmark 456 belongs to UserWord 789
  → UserWord 123's actual bookmarks: [111, 222]
```

**Cause:** Bookmark update created new UserWord but didn't clear old UserWord's reference

**Fix:** Set `preferred_bookmark_id = 111` (first actual bookmark)

### Issue 2: NULL preferred_bookmark

**Problem:**

```sql
UserWord 123: preferred_bookmark_id = NULL
  → But has bookmarks: [111, 222]
```

**Cause:** Bookmark creation didn't set preferred_bookmark_id

**Fix:** Set `preferred_bookmark_id = 111` (first bookmark)

### Issue 3: Orphaned UserWords

**Problem:**

```sql
UserWord 123: no bookmarks at all
```

**Cause:** All bookmarks deleted or moved to different UserWord

**Fix:** Delete UserWord and its schedule

## Performance Considerations

### Why NOT in Hot Path?

Previously, `validate_data_integrity()` was called in `as_dictionary()`:

- ❌ Called on **every API request** (word lists, exercises, etc.)
- ❌ Runs `self.bookmarks()` query every time
- ❌ Logs same warnings repeatedly
- ❌ Slows down API responses

**Solution:** Removed from hot path, rely on:

- Write-time prevention (SQLAlchemy listeners)
- Periodic batch checks (daily cron)

### Orphan Check Performance

The orphan check is slow because it requires a LEFT JOIN on all UserWords:

```sql
SELECT user_word.*
FROM user_word
         LEFT JOIN bookmark ON bookmark.user_word_id = user_word.id
GROUP BY user_word.id
HAVING COUNT(bookmark.id) = 0
```

**Recommendation:** Use `--skip-orphaned` flag for daily checks, run full check weekly.

## Monitoring

### Check Logs

```bash
# View daily check results
tail -f /var/log/zeeguu_integrity.log

# Check for issues in last 7 days
grep "Total issues found" /var/log/zeeguu_integrity.log | tail -7

# Check if cron is running
grep "zeeguu_integrity" /var/log/syslog
```

### Alert on Issues

```bash
# Example monitoring script
#!/bin/bash
ISSUES=$(python -m tools.user_word_integrity._daily_user_word_integrity_check 2>&1 | grep "Total issues found" | awk '{print $4}')
if [ "$ISSUES" -gt 0 ]; then
    echo "WARNING: Found $ISSUES integrity issues in Zeeguu database"
    # Send alert (email, Slack, etc.)
fi
```

## Write-Time Validation

**Location:** `zeeguu/core/model/user_word.py:430-462`

SQLAlchemy event listener validates `preferred_bookmark_id` before INSERT/UPDATE:

```python
@sqlalchemy.event.listens_for(UserWord, "before_insert")
@sqlalchemy.event.listens_for(UserWord, "before_update")
def validate_preferred_bookmark_before_write(mapper, connection, target):
    """Raises ValueError if preferred_bookmark_id is invalid"""
```

**This prevents corruption from happening in the first place.**

## Troubleshooting

### Issue: Cron not running

```bash
# Check cron is enabled
sudo systemctl status cron

# Check crontab is configured
crontab -l | grep integrity

# Test manually
cd /path/to/zeeguu/api
source ~/.venvs/z_env/bin/activate
python -m tools.user_word_integrity._daily_user_word_integrity_check --fix
```

### Issue: Permissions error

Make sure the cron user has:

- Read access to code
- Write access to database
- Write access to log file

### Issue: Too many warnings

If seeing repeated integrity warnings:

1. Run full check with `--fix` to clean up existing issues
2. Investigate why new issues are being created (check recent code changes)
3. Review write-time validation is working (test with `_test_integrity_validation.py`)

## Testing

**Test write-time validation:**

```bash
python -m tools.user_word_integrity._test_integrity_validation
# Should output: ✓ SUCCESS: Validation caught the error!
```

## Related Documentation

- [USER_BOOKMARK_USERWORD_ARCHITECTURE.md](../docs/USER_BOOKMARK_USERWORD_ARCHITECTURE.md) - Architecture overview
- [ABR 002](../docs/abr/002-userword-naming-and-fit-for-study-placement.md) - Naming analysis
