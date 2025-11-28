# Blockquote Implementation

## Overview

Blockquotes in Zeeguu articles are handled by flattening their structure into individual fragments, similar to how list items (`<li>`) are processed. This approach maintains consistency with the existing fragment system while enabling word-by-word translation within blockquotes.

## Architecture

### 1. Editor (Frontend)
**File:** `js/web/src/teacher/sharedComponents/RichTextEditor.js`

The Tiptap rich text editor allows users to create blockquotes with multiple paragraphs. The CSS styling mimics the reader's appearance:

```css
blockquote p {
  margin-left: 2em;
  padding: 1em 1.5em;
  border-left: 4px solid #ff8c00;
  background-color: #f9f9f9;
  font-style: italic;
}
```

- The `<blockquote>` container itself has no styling
- Each `<p>` inside gets the visual styling (border, background, italic)
- First `<p>` displays the opening quote mark (`"`)
- Paragraphs stack together to appear as one continuous blockquote

### 2. Saving to Database (Backend)
**File:** `zeeguu/core/model/article.py` - `create_article_fragments()` method

When an article is saved, the HTML is parsed and fragments are created:

```python
# Skip blockquote containers - we'll process their paragraph children instead
if element.name == 'blockquote':
    continue

# For paragraphs inside blockquotes, use special formatting
if element.name == 'p' and element.find_parent('blockquote'):
    tag_name = 'blockquote'
    text_content = element.get_text().strip()
```

**Key Points:**
- The `<blockquote>` container is **skipped** (not stored as a fragment)
- Each `<p>` inside the blockquote becomes a **separate fragment**
- These fragments are marked with `formatting='blockquote'`
- Plain text content is extracted (not HTML) to enable tokenization

**Example:**
```html
<!-- Input HTML -->
<blockquote>
  <p>First line of quote</p>
  <p>Second line of quote</p>
</blockquote>

<!-- Creates 2 fragments in database -->
Fragment 1: text="First line of quote", formatting="blockquote", order=0
Fragment 2: text="Second line of quote", formatting="blockquote", order=1
```

### 3. Rendering in Reader (Frontend)
**Files:**
- `js/web/src/reader/ArticleReader.js` - Maps fragments to `<TranslatableText>` components
- `js/web/src/reader/TranslatableText.js` - Renders individual fragments
- `js/web/src/reader/TranslatableText.sc.js` - Blockquote styling
- `js/web/src/reader/ArticleReader.sc.js` - CSS for merging consecutive blockquotes

Each fragment with `formatting='blockquote'` renders as a separate `<blockquote>` element wrapped in a `<div>`:

```jsx
{interactiveFragments.map((interactiveText, index) => (
  <TranslatableText
    key={index}
    interactiveText={interactiveText}
    // ... other props
  />
))}
```

The fragment's `formatting` property determines the HTML element type (`divType='blockquote'`), creating:

```html
<div><!-- TranslatableText wrapper -->
  <blockquote class="textParagraph blockquote">
    <z-tag>First</z-tag>
    <z-tag>line</z-tag>
    <!-- ... translatable words -->
  </blockquote>
</div>
<div><!-- Next TranslatableText wrapper -->
  <blockquote class="textParagraph blockquote">
    <z-tag>Second</z-tag>
    <z-tag>line</z-tag>
    <!-- ... translatable words -->
  </blockquote>
</div>
```

### 4. Visual Merging with CSS
**File:** `js/web/src/reader/ArticleReader.sc.js` - `MainText` styled component

Since each fragment creates a separate `<blockquote>` element, CSS is used to make consecutive blockquotes appear as one continuous quote:

```css
/* Consecutive blockquote fragments should merge visually */
> div:has(.textParagraph.blockquote) + div:has(.textParagraph.blockquote) {
  .textParagraph.blockquote {
    margin-top: 0;  /* Remove gap between consecutive blockquotes */
  }
  .textParagraph.blockquote::before {
    content: none;  /* Hide quote mark on non-first blockquotes */
  }
}

/* Last blockquote in sequence gets bottom margin */
> div:has(.textParagraph.blockquote):not(:has(+ div .textParagraph.blockquote)) {
  .textParagraph.blockquote {
    margin-bottom: 1.5em;
  }
}
```

**Result:**
- Consecutive blockquote fragments stack together with no gaps
- Only the first displays the opening quote mark
- Only the last has bottom margin
- Visually appears as one continuous blockquote
- Each word remains translatable via the `<z-tag>` tokenization

## Consistency with Lists

This implementation mirrors how list items are handled:

| Feature | Lists (`<li>`) | Blockquotes (`<blockquote>`) |
|---------|---------------|------------------------------|
| **Container stored?** | No (`<ul>`/`<ol>` skipped) | No (`<blockquote>` skipped) |
| **Individual items stored?** | Yes (each `<li>`) | Yes (each `<p>`) |
| **Formatting tag** | `'li'` | `'blockquote'` |
| **Visual merging** | Consecutive `li` elements | CSS merges consecutive blockquotes |
| **Translatable?** | ✓ Yes | ✓ Yes |

## Benefits

1. **Translatable Content**: All text within blockquotes can be clicked for word-by-word translation
2. **Consistent Architecture**: Same pattern as lists, no special-case code
3. **No HTML in Database**: Plain text stored, not HTML strings
4. **Flexible Rendering**: Frontend controls visual presentation via CSS

## Limitations

1. **No Parent-Child Relationship**: Cannot query "all fragments belonging to this blockquote"
2. **CSS Dependency**: Visual merging relies on CSS sibling selectors (`:has()`)
3. **Order Matters**: Fragments must be in sequence for proper rendering
4. **Lost Structure**: Cannot distinguish between one blockquote with 3 paragraphs vs. three separate single-paragraph blockquotes

## Future Work

### Parent-Child Fragment Relationships

A more sustainable long-term solution would be to add explicit parent-child relationships to the fragment model:

#### Schema Changes
```sql
ALTER TABLE article_fragment
ADD COLUMN parent_fragment_id INT DEFAULT NULL,
ADD FOREIGN KEY (parent_fragment_id) REFERENCES article_fragment(id);
```

#### Benefits

1. **Explicit Structure Preservation**
   - Store container elements (`<blockquote>`, `<ul>`, `<ol>`) as parent fragments
   - Child fragments (`<p>`, `<li>`) reference their parent
   - Query: "Give me all paragraphs in this blockquote"

2. **Better Data Modeling**
   ```python
   # Query all fragments in a specific blockquote
   blockquote_paragraphs = ArticleFragment.query.filter_by(
       parent_fragment_id=blockquote_fragment.id
   ).order_by(ArticleFragment.order).all()
   ```

3. **Richer Operations**
   - Delete a blockquote and all its paragraphs in one operation
   - Reorder paragraphs within a blockquote
   - Distinguish between nested structures (lists inside blockquotes)

4. **Frontend Simplification**
   - No CSS hacks for visual merging
   - Render true nested HTML structure
   - Easier to maintain and reason about

#### Implementation Approach

1. **Migration Strategy**
   - Add `parent_fragment_id` column (nullable)
   - Migrate existing data: detect consecutive fragments with same formatting
   - Create parent fragments for detected groups

2. **Fragment Creation**
   ```python
   # Create parent blockquote fragment
   blockquote_fragment = ArticleFragment.create(
       article=article,
       text="",  # Container has no text
       order=order,
       formatting="blockquote-container"
   )

   # Create child paragraph fragments
   for p in blockquote.find_all('p'):
       ArticleFragment.create(
           article=article,
           text=p.get_text(),
           order=child_order,
           formatting="p",
           parent_fragment_id=blockquote_fragment.id
       )
   ```

3. **Frontend Rendering**
   ```jsx
   // Render with proper nesting
   if (fragment.has_children) {
     return (
       <blockquote>
         {fragment.children.map(child => (
           <TranslatableText interactiveText={child} />
         ))}
       </blockquote>
     );
   }
   ```

#### Trade-offs

**Pros:**
- Clean, explicit data model
- Easier to query and manipulate
- No CSS tricks needed
- Supports arbitrary nesting depth

**Cons:**
- Requires database migration
- More complex fragment creation logic
- Need to handle backward compatibility
- Changes to fragment querying throughout codebase

### Recommendation

The current flat structure works well for the immediate use case and maintains consistency with existing patterns. However, if the application needs to support:
- More complex nested structures (e.g., blockquotes with lists inside)
- Structural operations (moving/deleting/reordering blocks)
- Better semantic understanding of content structure

Then implementing parent-child relationships would be worthwhile. This would be a good candidate for a future refactoring when those needs arise.
