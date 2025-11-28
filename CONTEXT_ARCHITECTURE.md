# Context Architecture Documentation

## Overview
This document explains the context system in Zeeguu - why it exists and how it works.

## The Problem
When users bookmark words, those words exist in **different types of sources**:
- Article paragraphs
- Article titles  
- Video titles
- Video captions
- AI-generated examples
- User-uploaded examples

Each source type has **different metadata and relationships** that need to be tracked.

## The Solution: Two-Layer Architecture

### 1. **BookmarkContext** (The Text)
- Stores the actual text content where the word appeared
- Language, sentence position, token position
- **Generic** - same structure for all source types

### 2. **Context Mapping Tables** (The Source)
- **ArticleFragmentContext**: Links bookmark → specific article paragraph
- **VideoTitleContext**: Links bookmark → specific video
- **ExampleSentenceContext**: Links bookmark → specific example sentence
- **Source-specific** - each has different fields and relationships

### 3. **ContextIdentifier** (The Coordinator)
- Contains IDs pointing to the actual sources
- Knows how to create the right mapping
- **Routing logic** - "this bookmark came from article 123" vs "this came from example sentence 456"

## Why This Complexity?

**Without it, you'd need:**
- Either one giant table with nullable columns for every possible source type (messy)
- Or duplicate the same bookmark/context logic in every source type (DRY violation)

**With it, you get:**
- Clean separation: text content vs source metadata
- Extensible: new source types don't break existing code
- Reusable: same text can appear in multiple sources
- Queryable: "show me all bookmarks from this video" or "all AI examples for this word"

## Real-world Usage Examples
- "Show user all words they learned from videos"
- "Find better example sentences for this word"
- "Which articles contain bookmarks for advanced learners"
- "Generate analytics on learning sources"

## Database Schema

```
BookmarkContext (generic text storage)
├── id
├── text (the actual sentence)
├── language_id
├── context_type_id
├── sentence_i, token_i (word position)
└── left_ellipsis, right_ellipsis

Context Mapping Tables (source-specific)
├── ArticleFragmentContext
│   ├── bookmark_id → Bookmark
│   └── article_fragment_id → ArticleFragment
├── VideoTitleContext  
│   ├── bookmark_id → Bookmark
│   └── video_id → Video
└── ExampleSentenceContext
    ├── bookmark_id → Bookmark
    └── example_sentence_id → ExampleSentence

ContextIdentifier (coordination)
├── context_type
├── article_fragment_id (if article context)
├── video_id (if video context)  
├── example_sentence_id (if example context)
└── create_context_mapping() method
```

## Code Flow

1. **Create source object** (Article, Video, ExampleSentence, etc.)
2. **Create ContextIdentifier** with source ID
3. **Create Bookmark** with ContextIdentifier
4. **ContextIdentifier.create_context_mapping()** creates the appropriate mapping table entry

## Benefits

The complexity enables powerful features while keeping the code organized and maintainable:

- **Separation of Concerns**: Text storage vs source metadata
- **Extensibility**: New source types don't break existing code
- **Reusability**: Same text can appear in multiple sources
- **Queryability**: Rich analytics and filtering capabilities
- **Type Safety**: Each source type has its own structure and validation