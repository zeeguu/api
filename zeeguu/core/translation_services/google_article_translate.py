"""
Whole-article translation with Google Translate (Cloud Translation v2).

The article goes in as Markdown and Google gets it as HTML (markdown_to_html,
format=html), so its headings, lists and quotes come back as the same tags and
are turned back into Markdown here, as deepl_translate_article does.

Google recommends at most 5,000 characters per request and takes at most 128
segments, so the article's blocks go in batches, and a paragraph longer than
that goes as several pieces cut at sentence ends and is put back together.
https://cloud.google.com/translate/docs/reference/rest/v2/translate
"""

import logging
import re
import time
from html import escape, unescape
from typing import List, Optional, Tuple

import requests

from python_translators.config import get_key_from_config

logger = logging.getLogger(__name__)

GOOGLE_V2_URL = "https://translation.googleapis.com/language/translate/v2"
MAX_CHARS_PER_REQUEST = 5000
MAX_SEGMENTS_PER_REQUEST = 128
TIMEOUT_SECONDS = 30
# For the whole article: past this, the caller's LLM fallback takes over.
DEADLINE_SECONDS = 60

# Our codes where Google's differ
GOOGLE_CODES = {"ind": "id"}

SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def _api_key() -> Optional[str]:
    try:
        return get_key_from_config("GOOGLE_TRANSLATE_API_KEY")
    except Exception:
        return None


def _google_code(code: str) -> str:
    return GOOGLE_CODES.get(code, code)


def _pieces(text: str, limit: int = MAX_CHARS_PER_REQUEST) -> List[str]:
    """text cut into pieces of at most `limit` characters, at sentence ends where it can be, else at spaces."""
    units = []
    for sentence in SENTENCE_END.split(text):
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            units.append(sentence[:cut])
            sentence = sentence[cut:].lstrip()
        units.append(sentence)

    pieces, piece = [], ""
    for unit in units:
        if piece and len(piece) + 1 + len(unit) > limit:
            pieces.append(piece)
            piece = unit
        else:
            piece = f"{piece} {unit}" if piece else unit
    if piece:
        pieces.append(piece)
    return pieces


def _segments(markdown: str) -> Tuple[List[str], List[int]]:
    """
    The HTML segments to send, and how many segments make up each block.

    A block is one segment unless it is a paragraph longer than a request:
    then its text goes as several pieces, to be joined back into one <p>.
    """
    from zeeguu.core.content_cleaning.html_to_markdown import markdown_to_html

    segments, sizes = [], []
    for block in markdown.split("\n\n"):
        html = markdown_to_html(block)
        if not html:
            continue
        if len(html) > MAX_CHARS_PER_REQUEST and html.startswith("<p>") and html.endswith("</p>"):
            pieces = _pieces(html[len("<p>") : -len("</p>")])
        else:
            pieces = [html]
        segments += pieces
        sizes.append(len(pieces))
    return segments, sizes


def _join(translated: List[str], sizes: List[int]) -> str:
    html, at = [], 0
    for size in sizes:
        if size == 1:
            html.append(translated[at])
        else:
            html.append("<p>" + " ".join(translated[at : at + size]) + "</p>")
        at += size
    return "".join(html)


def _batches(segments: List[str]) -> List[List[str]]:
    """Consecutive segments, cut where a batch would pass either request limit."""
    batches, batch, size = [], [], 0
    for segment in segments:
        if batch and (size + len(segment) > MAX_CHARS_PER_REQUEST or len(batch) == MAX_SEGMENTS_PER_REQUEST):
            batches.append(batch)
            batch, size = [], 0
        batch.append(segment)
        size += len(segment)
    if batch:
        batches.append(batch)
    return batches


def _translate_segments(segments: List[str], source_language: str, target_language: str, key: str) -> List[str]:
    deadline = time.monotonic() + DEADLINE_SECONDS
    translated = []
    for batch in _batches(segments):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"no answer within {DEADLINE_SECONDS}s")
        response = requests.post(
            GOOGLE_V2_URL,
            # In a header, not the URL: requests puts the URL in its errors, and we log those.
            headers={"X-Goog-Api-Key": key},
            data={
                "q": batch,
                "source": _google_code(source_language),
                "target": _google_code(target_language),
                "format": "html",
            },
            timeout=min(TIMEOUT_SECONDS, remaining),
        )
        if not response.ok:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
        translations = [t["translatedText"] for t in response.json()["data"]["translations"]]
        if len(translations) != len(batch):
            raise RuntimeError(f"sent {len(batch)} segments, got {len(translations)} translations")
        translated += translations
    return translated


def google_translate_article(title: str, markdown: str, source_language: str, target_language: str) -> Optional[dict]:
    """
    Returns:
        dict with 'title' and 'content' (Markdown), or None if Google is not
        configured or the call failed -- the caller then translates with an LLM.
    """
    key = _api_key()
    if not key:
        return None

    from zeeguu.core.content_cleaning.html_to_markdown import html_to_markdown

    segments, sizes = _segments(markdown)
    try:
        translated_title, *translated = _translate_segments(
            [escape(title or "")] + segments, source_language, target_language, key
        )
    except Exception as e:
        logger.warning(f"Google article translation {source_language}->{target_language} failed: {e}")
        return None

    content = html_to_markdown(_join(translated, sizes))
    if not content.strip():
        return None
    return {"title": unescape(translated_title).strip(), "content": content}
