# Refactoring TODO List

## 1. Rename Context Mapping Classes

**Problem:** Current naming pattern `<Source>Context` is confusing and unclear about purpose.

**Current names:**
- `ExampleSentenceContext`
- `ArticleFragmentContext`
- `VideoTitleContext`
- `VideoCaptionContext`

**Proposed names:** `Bookmark<Source>` pattern
- `BookmarkExampleSentence`
- `BookmarkArticleFragment` 
- `BookmarkVideoTitle`
- `BookmarkVideoCaption`

**Why this is better:**
- Clear relationship direction: "This is a bookmark linked to an example sentence"
- Consistent naming pattern
- Follows database junction table conventions
- Searchable - easy to find all bookmark-related mappings
- Less confusion with actual context (the text content)

**Impact:**
- Rename all context mapping classes and their files
- Update all imports across codebase
- Update database table names (migration required)
- Update ContextType.get_table_corresponding_to_type() method
- Update documentation

**Priority:** Medium - improves code clarity but not urgent functionality