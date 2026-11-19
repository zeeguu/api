"""
Whole-article translation with Google Translate (Cloud Translation v2).

The article goes in as Markdown and Google gets it as HTML (markdown_to_html,
format=html), so its headings, lists and quotes come back as the same tags and
are turned back into Markdown here, as deepl_translate_article does. Google
detects the source language: the one we hold comes from langdetect.

Google recommends at most 5,000 characters per request and takes at most 128
segments, so the article's blocks go in batches.
https://cloud.google.com/translate/docs/reference/rest/v2/translate
"""

import logging
from html import escape, unescape
from typing import List, Optional

import requests

from python_translators.config import get_key_from_config

logger = logging.getLogger(__name__)

GOOGLE_V2_URL = "https://translation.googleapis.com/language/translate/v2"
MAX_CHARS_PER_REQUEST = 5000
MAX_SEGMENTS_PER_REQUEST = 128
TIMEOUT_SECONDS = 30


def _api_key() -> Optional[str]:
    try:
        return get_key_from_config("GOOGLE_TRANSLATE_API_KEY")
    except Exception:
        return None


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


def _translate_segments(segments: List[str], target_language: str, key: str) -> List[str]:
    translated = []
    for batch in _batches(segments):
        response = requests.post(
            GOOGLE_V2_URL,
            params={"key": key},
            data={"q": batch, "target": target_language, "format": "html"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        translated += [t["translatedText"] for t in response.json()["data"]["translations"]]
    return translated


def google_translate_article(title: str, markdown: str, target_language: str) -> Optional[dict]:
    """
    Returns:
        dict with 'title' and 'content' (Markdown), or None if Google is not
        configured or the call failed -- the caller then translates with an LLM.
    """
    key = _api_key()
    if not key:
        return None

    from zeeguu.core.content_cleaning.html_to_markdown import html_to_markdown, markdown_to_html

    blocks = [html for html in (markdown_to_html(block) for block in markdown.split("\n\n")) if html]
    try:
        translated_title, *translated_blocks = _translate_segments([escape(title or "")] + blocks, target_language, key)
    except Exception as e:
        logger.warning(f"Google article translation into {target_language} failed: {e}")
        return None

    content = html_to_markdown("".join(translated_blocks))
    if not content.strip():
        return None
    return {"title": unescape(translated_title).strip(), "content": content}
