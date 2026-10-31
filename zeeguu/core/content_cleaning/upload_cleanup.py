"""
Remove the page furniture from an upload before anyone reads it: captions, "Læs også" boxes, ads, consent
dialogs, paywall prompts, quizzes. Uploads skip the crawler's cleaning (readability-server and its per-site
rules), since their HTML comes from the extension's Readability.

DeepSeek reads the upload's Markdown blocks, the same the simplifier gets, and says which to drop. The
dropped blocks and the figures go from raw_html, and text_content becomes the text of what is left, so the
original, the simplified and the translated versions are all made from the cleaned page. What was removed is
kept in article_upload_cleanup and article_upload_block.

Eval set, prompt history and results (DeepSeek, prompt 4: precision 0.976, recall 0.982 on 41 uploads):
zeeguu-experiments, upload-cleanup/2026-10-31-block-labels. Change the prompt there first.
"""
import json
import time

from bs4 import BeautifulSoup

from zeeguu.core.content_cleaning.html_to_markdown import unescape_marker
from zeeguu.core.llm_services import models
from zeeguu.logging import log

PROMPT_VERSION = 4
MODEL = models.DEEPSEEK_GENERAL
TIMEOUT = 30

REASONS = {
    "embed_placeholder": "text that stands in for an embed the page could not show: cookie-consent notices, 'enable JavaScript', 'watch on YouTube'",
    "caption_credit": "a photo, video or graphic caption, or a credit line (Foto:, Illustration:, Video:)",
    "editorial_note": "a correction, update or disclosure note about the article rather than part of the story",
    "ad": "an ad or its label (Annonce, Advertisement, Sponsored)",
    "related_links": "links, headings or teasers pointing to other articles: Læs også, Read more, Related, Mest læste, even when the links themselves are gone. A teaser box goes whole: its heading, its summary paragraph and its link",
    "duplicate": "a title, standfirst or pull quote that repeats text the article already has elsewhere. A pull quote is a sentence of the article repeated as a quote or highlighted line. Only text repeated word for word or nearly is a duplicate: a block that says the same thing in other words is story",
    "listen_share": "listen, share, save, print, comment or follow buttons and prompts",
    "subscribe": "newsletter, subscription, login or paywall prompts",
    "meta": "bylines, author bios, dates, reading time, tags, breadcrumbs, copyright",
    "consent_dialog": "a cookie or privacy dialog captured with the page",
    "other": "other page furniture that is not the story; say what it is in the note",
}

SYSTEM = f"""You label the blocks of a news article that a language learner saved from a web page. A learner
will read the article, simplified to their level, and only the story should reach them. Some blocks are page
furniture the extraction kept. Decide which blocks to drop.

You get the title and the numbered blocks ([k] before each). Drop a block only when it is not part of the story
as its author wrote it, and give the reason:

{chr(10).join(f"- {name}: {meaning}" for name, meaning in REASONS.items())}

Keep everything that is the story: its paragraphs, headings, quotes, lists, fact boxes and interview questions,
and a lead or standfirst. The standfirst and the first paragraphs are story even when they are short or restate
the title. When in doubt, keep the block: a dropped story paragraph hurts the learner more than a
kept caption. A block that mixes story text and furniture is kept; say so in mixed_blocks.

Not every page is a news article: a guide, a course page, a product page or a story collection keeps its own
text the same way, even when it reads like instructions or a list. Drop only the furniture around it, and the
page's widgets: a quiz with answer options and score counters, player controls, forms.

Also say whether the article is incomplete: the story refers to something the learner will not see that it
depends on (a video, a chart, an interactive, a gallery, a list that is not there), or the text breaks off.
A passing mention of a video next to a full story is not incomplete. Most articles are complete.

Reply with one json object and nothing else:
{{"drops": [{{"block": <k>, "reason": <one of {", ".join(REASONS)}>, "note": <a few words>}}],
 "mixed_blocks": [<k>, ...], "incomplete": <true or false>, "incomplete_note": <why, or "">}}"""

# The Markdown markers a block can open with (html_to_markdown._marker): "## ", "### ", "- ", "1. ", "> ".
BLOCK_MARKERS = ("### ", "## ", "- ", "1. ", "> ")


def cleanup_upload(session, upload):
    """Clean the upload in place. Raises when the classifier fails; the upload is then left as it came."""
    from zeeguu.core.llm_services.deepseek_service import DeepSeekService
    from zeeguu.core.model.article_upload_cleanup import ArticleUploadBlock, ArticleUploadCleanup

    markdown = upload.markdown_from_html()
    if not markdown:
        return  # a partial extraction: its text is not in the HTML, so there is nothing to remove it from
    blocks = markdown.split("\n\n")
    language = upload.language.code if upload.language else "unknown"

    started = time.monotonic()
    reply = DeepSeekService(timeout=TIMEOUT)._make_deepseek_request(
        {"system": SYSTEM, "user": f"Language: {language}\nTITLE: {upload.title or ''}\n\n{numbered(blocks)}"},
        max_tokens=8000,
        temperature=0,
        json_output=True,
    )
    verdict = json.loads(reply)
    seconds = round(time.monotonic() - started, 2)
    drops = {d["block"]: d for d in verdict["drops"] if 0 <= d["block"] < len(blocks)}

    cleaned = clean_html(upload.raw_html, [blocks[k] for k in drops], [b for k, b in enumerate(blocks) if k not in drops])
    session.add(ArticleUploadCleanup(
        upload, upload.raw_html, upload.text_content, bool(verdict.get("incomplete")),
        verdict.get("incomplete_note") or None, MODEL, PROMPT_VERSION, seconds,
    ))
    for k, block in enumerate(blocks):
        drop = drops.get(k, {})
        session.add(ArticleUploadBlock(upload, k, block, k not in drops, drop.get("reason"), drop.get("note")))
    upload.raw_html = cleaned
    upload.text_content = BeautifulSoup(cleaned, "html.parser").get_text()
    session.add(upload)
    session.commit()
    log(f"upload {upload.id} cleaned in {seconds}s: dropped {len(drops)} of {len(blocks)} blocks")


def numbered(blocks):
    return "\n\n".join(f"[{k}] {block}" for k, block in enumerate(blocks))


def clean_html(html, dropped, kept):
    """``html`` without its figures and without the elements that hold exactly the text of a dropped block.

    A text that is also a kept block stays (the page has it twice: "Læs også" as furniture and as story is
    rare, but a wrong cut loses story). A dropped block that no element holds alone (part of a <p> split
    by <br>) stays too."""
    soup = BeautifulSoup(html, "html.parser")
    for figure in soup.find_all("figure"):
        figure.decompose()

    targets = {_letters(_text_of(b)) for b in dropped} - {_letters(_text_of(b)) for b in kept} - {""}
    matched = [el for el in soup.find_all(True) if _letters(el.get_text()) in targets]
    matched_ids = {id(el) for el in matched}
    for el in matched:
        if not any(id(parent) in matched_ids for parent in el.parents):
            el.extract()
    return str(soup)


def _text_of(block):
    # the block's text as the HTML has it: without its Markdown marker or escape
    for marker in BLOCK_MARKERS:
        if block.startswith(marker):
            return block[len(marker):]
    return unescape_marker(block)


def _letters(text):
    # Markdown and HTML space the same text differently (table cells, inline tags, line breaks)
    return "".join(text.split())
