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


from html import escape

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

# A figure goes whole, as the crawler's readability-server drops it: its
# caption and credit, and the fallback text an embedded video leaves when its
# cookies are refused ("Hov! Her ligger et element fra en tjeneste, der bruger
# cookies", videnskab.dk). Not a form: some sites wrap the whole article in one.
DROPPED = {
    "script", "style", "noscript", "template", "img", "picture", "source",
    "svg", "video", "audio", "iframe", "button", "input", "select", "textarea",
    "figure",
}

# What a paragraph can open with that Markdown reads as structure: a list item
# (-, *, +, or a number with . or ), as in "1." and "1)"), a heading (#, ##, ...)
# or a quote (>). Each is followed by a space. "- Jeg er bange", the dash that
# opens a line of speech in Danish, French and other languages, would otherwise
# become a bullet.
MARKER_SYMBOLS = {"-", "*", "+", "#", ">"}
NUMBER_ENDS = {".", ")"}
DIGITS = "0123456789"


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
        blocks.append(escape_marker(text))


def escape_marker(text: str) -> str:
    """
    `text`, with the marker it opens with (see MARKER_SYMBOLS) escaped so that
    it reads as text: \\- Jeg er bange, \\## Tre ting, 1\\. maj. A number is escaped
    after its digits: markdown2 reads 1\\. as "1." but shows \\1. as it is.
    """
    marker = _opening_marker(text)
    if not marker:
        return text
    at = len(marker) - 1 if marker[-1] in NUMBER_ENDS else 0
    return text[:at] + "\\" + text[at:]


def unescape_marker(text: str) -> str:
    """The inverse of escape_marker."""
    at = len(text) - len(text.lstrip(DIGITS))
    escapable = NUMBER_ENDS if at else MARKER_SYMBOLS
    if text[at : at + 1] == "\\" and text[at + 1 : at + 2] in escapable:
        return text[:at] + text[at + 1 :]
    return text


def _opening_marker(text: str) -> str:
    """The marker `text` opens with ("-", "##", "12."), or "" if it opens with text."""
    digits = len(text) - len(text.lstrip(DIGITS))
    if digits:
        marker = text[: digits + 1] if text[digits : digits + 1] in NUMBER_ENDS else ""
    elif text[:1] in MARKER_SYMBOLS:
        marker = text[: len(text) - len(text.lstrip(text[0]))]  # ## is a heading too
    else:
        marker = ""
    return marker if text[len(marker) : len(marker) + 1].isspace() else ""


# The markers html_to_markdown writes, and the element each stands for
BLOCK_TAGS = [("### ", "h3"), ("## ", "h2"), ("- ", "ul"), ("1. ", "ol"), ("> ", "blockquote")]


def markdown_to_html(markdown: str) -> str:
    """
    The inverse of html_to_markdown, for a translator that keeps HTML tags
    (DeepL): each block becomes the element its marker names, and the text is
    escaped. A Markdown renderer would read more into plain text than that:
    "5. maj kom freden" as a list starting at 5, foo_bar_baz as emphasis.
    """
    html = []
    for block in markdown.split("\n\n"):
        block = " ".join(block.split())
        if not block:
            continue
        tag = next((t for marker, t in BLOCK_TAGS if block.startswith(marker)), None)
        if tag in ("ul", "ol"):
            html.append(f"<{tag}><li>{escape(block[3 if tag == 'ol' else 2:])}</li></{tag}>")
        elif tag:
            html.append(f"<{tag}>{escape(block.split(' ', 1)[1])}</{tag}>")
        else:
            html.append(f"<p>{escape(unescape_marker(block))}</p>")
    return "".join(html)
