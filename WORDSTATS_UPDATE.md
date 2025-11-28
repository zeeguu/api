# Wordstats Update - October 2025

## Summary

Updated `python-wordstats` to use full frequency lists with 10x more word coverage.

## Changes

### Before
- Used hermitdave 2016 50k word lists
- Loaded only top 10,000 words per language
- Many medium-frequency words had rank=100000 (unknown)

### After
- Uses hermitdave 2018 full word lists
- Loads ~100k-250k words per language (filtered by MIN_OCCURRENCE_COUNT ≥ 10)
- Much better coverage for medium and low-frequency words

### Example (Danish)
| Word | Occurrences | Before | After |
|------|-------------|--------|-------|
| ikke | 1,928,834 | rank=5 | rank=5 ✓ |
| omfatte | 45 | rank=100000 ❌ | rank=33596 ✓ |
| skorter | 11 | rank=100000 ❌ | rank=88912 ✓ |

## Configuration

### Development (default)
```python
# default_api.cfg
PRELOAD_WORDSTATS=False  # Lazy loading - fast startup
```
- Languages load on first use (~1 second per language)
- Good for development: fast restarts, no waiting

### Production (recommended)
```python
# production_api.cfg
PRELOAD_WORDSTATS=True  # Preload at startup
```
- All languages load at startup (~10-30 seconds total)
- No first-request delays
- Recommended for production

## Implementation

The preloading logic is in `zeeguu/api/app.py`:
```python
if app.config.get("PRELOAD_WORDSTATS", False):
    from wordstats import LanguageInfo
    from zeeguu.core.model import Language

    all_languages = Language.all_languages()
    language_codes = [lang.code for lang in all_languages]
    LanguageInfo.load_in_memory_for(language_codes)
```

## Memory Impact

Approximate memory per language (with MIN_OCCURRENCE_COUNT=10):
- Danish: ~10 MB (99k words)
- English: ~25 MB (241k words)
- Total for all languages: ~150-200 MB

This is acceptable for modern production servers.

## Migration

After deploying the updated wordstats:

1. **Recalculate phrase ranks** (already done):
   ```bash
   source ~/.venvs/z_env/bin/activate
   python tools/migrations/25-10-22--recalculate_all_multiword_phrase_ranks.py
   ```

2. **Update production config**:
   - Set `PRELOAD_WORDSTATS=True` in production config
   - Keep `PRELOAD_WORDSTATS=False` in development

3. **Restart API** and verify startup logs:
   ```
   *** Wordstats preloaded 15 languages in 18.45s
   ```

## Benefits

1. **Better word prioritization**: Words like "omfatte" and "skorter" now have accurate ranks
2. **Improved learning experience**: Better difficulty estimates for spaced repetition
3. **Configurable preloading**: Fast development, optimized production
4. **Language-independent**: MIN_OCCURRENCE_COUNT=10 works well across all languages (~14-15% of corpus)
