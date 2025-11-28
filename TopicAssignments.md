# Topic Assignment System in Zeeguu

## Overview
Articles in Zeeguu are assigned topics through a three-tier priority system, though in practice only semantic inference is currently functional for new articles.

## Topic Assignment Methods

### 1. Hardcoded Feed Topics (HARDSET - Origin Type 2)
- Certain feeds have predefined topic assignments
- Examples:
  - The Onion (Feed ID 102) → Satire (Topic ID 8)
  - Lercio (Feed ID 121) → Satire (Topic ID 8)
- **Status**: ✅ Working (534 articles)
- Implemented in: `article_downloader.py` lines 397-409

### 2. URL Keyword-Based Topics (URL_PARSED - Origin Type 1)
- Extracts keywords from article URLs (e.g., `/politics/article` → "politics")
- Maps keywords to topics via `url_keyword` table
- **Status**: ❌ Mostly broken for new articles
- **Issues**:
  - Only 386 of 13,388 URL keywords have topic mappings
  - Common mappings that exist: "football"→Sports, "politics"→Politics, "culture"→Culture & Art
  - 421,444 historical articles have URL-based topics (from migration scripts)
  - New articles don't get URL-based topics (0 recent articles use this method)
- Implemented in: `article_downloader.py` lines 412-435

### 3. Content-Based Inference (INFERRED - Origin Type 3)
- Uses semantic similarity via Elasticsearch with dense vectors
- Process:
  1. Generate embedding for article content
  2. Find 9 most similar articles using KNN search
  3. Collect topics from similar articles
  4. If most common topic appears in ≥50% of neighbors, assign it
- **Status**: ✅ Working (319,706 articles, all new articles use this)
- Implemented in: `article_downloader.py` lines 440-450, `elastic_semantic_search.py`

## Current State Summary

### Database Statistics
- **Total URL keywords**: 13,388
- **Keywords with topics**: 386
- **Keywords without topics**: 13,002
- **Articles with URL-parsed topics**: 421,444 (historical, from migration)
- **Articles with inferred topics**: 319,706 (including all new articles)
- **Articles with hardset topics**: 534

### What Actually Happens for New Articles
1. Check if feed is hardcoded (rarely)
2. Extract URL keywords but usually find no topic mapping
3. Fall back to semantic inference (this is what actually assigns topics)
4. All recent articles show `origin_type = 3` (INFERRED)

## Historical Context
The URL keyword system was populated via migration scripts during the transition to the new topic system (see `UpdateToTopics.md`). The process involved:
1. Extracting URL keywords from existing articles
2. Manually mapping frequent keywords (>100 occurrences) to topics
3. Running `set_new_topics_from_url_keyword.py` to retroactively assign topics

However, this mapping process was never completed comprehensively, leaving most URL keywords without topic assignments.

## Files Involved
- `zeeguu/core/content_retriever/article_downloader.py` - Main topic assignment logic
- `zeeguu/core/model/url_keyword.py` - URL keyword extraction
- `zeeguu/core/model/topic.py` - Topic model
- `zeeguu/core/model/article_topic_map.py` - Article-topic relationships
- `zeeguu/core/semantic_search/elastic_semantic_search.py` - Inference logic
- `tools/old/es_v8_migration/` - Historical migration scripts