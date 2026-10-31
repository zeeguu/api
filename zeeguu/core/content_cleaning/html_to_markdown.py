"""
An article's HTML as Markdown, for the LLMs that rewrite it.

Readability's HTML keeps what plain text loses: which blocks are headings, list
items and quotes, and where one paragraph ends and the next begins. Its
textContent glues paragraphs together and flattens the rest, so a simplifier
that reads it cannot keep a heading a heading.

Only the structure is kept. Links become their text, emphasis is dropped, and
images, scripts and embeds go.

Why not markdownify: compared on the 40 uploads of the 2026-10-30 eval
(zeeguu-experiments, simplification/2026-10-30-markdown-input). Matching what
the simplifier needs (one block per paragraph, list item and table row; text
without emphasis or links; only a leading marker escaped, where its
escape_misc escapes [, ], &, + and | anywhere) took a 55-line subclass, most
of what this module is. It then gave the same Markdown for 31 uploads and
worse for 5: list
items without their marker, a heading inside a list item split into
"- ###" and "###", table cells glued into one word.
"""

import re

from bs4 import BeautifulSoup, NavigableString, Tag

HEADINGS = {"h1": "##", "h2": "##", "h3": "###", "h4": "###", "h5": "###", "h6": "###"}

# Elements that start a new block of text. A table row is one block, its cells
# separated by spaces.
BLOCKS = {
    "address", "article", "aside", "blockquote", "dd", "div", "dl", "dt",
    "figcaption", "figure", "footer", "header", "li", "main", "nav", "ol",
    "p", "pre", "section", "table", "tr", "ul",
} | set(HEADINGS)
CELLS = {"td", "th"}

# Not a form: some sites wrap the whole article in one
DROPPED = {
    "script", "style", "noscript", "template", "img", "picture", "source",
    "svg", "video", "audio", "iframe", "button", "input", "select", "textarea",
}

# A paragraph that starts like this would turn into a list, a heading or a quote
# when read back as Markdown: "- Jeg er bange", the dash that opens a line of
# speech in Danish, French and other languages, would become a bullet. A number
# is escaped after its digits (1\. maj): markdown2 reads that back as "1. maj",
# but shows \1. as it is.
MARKDOWN_PREFIX = re.compile(r"^(?:([-*+#>])|(\d+)([.)]))(?=\s)")


def html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for dropped in soup.find_all(DROPPED):
        dropped.decompose()
    blocks = []
    _walk(soup, None, blocks, [])
    return "\n\n".join(blocks)


def _walk(node, marker, blocks, inline):
    """
    Append the Markdown blocks of `node`'s children to `blocks`. `marker` is
    what a block of text inside it starts with: a heading's ##, a list item's -,
    a quote's >. Text not yet ended by a block element collects in `inline`.
    """
    for child in node.children:
        if isinstance(child, NavigableString):
            if child.__class__ is NavigableString:  # not a comment or a doctype
                inline.append(str(child))
            continue
        if not isinstance(child, Tag):
            continue
        if child.name == "br":
            # lines of dialogue, verse, an address: each its own paragraph.
            # html.parser can nest the text after a <br/> inside it.
            _flush(inline, marker, blocks)
            _walk(child, marker, blocks, inline)
            continue
        if child.name in CELLS:
            _walk(child, marker, blocks, inline)
            inline.append(" ")
            continue
        if child.name not in BLOCKS:
            _walk(child, marker, blocks, inline)
            continue
        _flush(inline, marker, blocks)
        _walk(child, _marker(child, marker), blocks, inline)
        _flush(inline, _marker(child, marker), blocks)


def _marker(element, outer):
    if element.name in HEADINGS:
        return HEADINGS[element.name]
    if element.name == "li":
        if element.parent is not None and element.parent.name == "ol":
            return "1."
        return "-"
    if element.name == "blockquote":
        return ">"
    return outer


def _flush(inline, marker, blocks):
    text = " ".join("".join(inline).split())
    inline.clear()
    if not text:
        return
    if marker:
        blocks.append(f"{marker} {text}")
    else:
        blocks.append(MARKDOWN_PREFIX.sub(_escaped, text))


def _escaped(match):
    symbol, digits, after_digits = match.groups()
    return f"\\{symbol}" if symbol else f"{digits}\\{after_digits}"
