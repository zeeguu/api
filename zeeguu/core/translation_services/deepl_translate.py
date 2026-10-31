"""
DeepL contextual translation.

DeepL's `/v2/translate` accepts a `context` parameter that carries the
surrounding sentence without translating it — purpose-built for translating
a single word in context. Unlike Google/Azure, we don't have to wrap the
word in <b>…</b> tags inside the sentence.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """Lazy-init the DeepL client; return None if no API key is configured."""
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("DEEPL_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        import deepl

        _client = deepl.Translator(api_key)
        return _client
    except Exception as e:
        logger.warning(f"DeepL client init failed: {e}")
        return None


def _to_deepl_target_lang(code: str) -> str:
    """DeepL requires a regional variant for some target languages."""
    code_upper = code.upper()
    return {
        "EN": "EN-US",
        "PT": "PT-PT",
    }.get(code_upper, code_upper)


def deepl_contextual_translate(data: dict) -> Optional[dict]:
    """
    Translate a word using DeepL with sentence context.

    Args:
        data: dict with 'source_language', 'target_language', 'word',
              'context' keys (matches the shape used by the Azure/Google
              translators in translator.py).

    Returns:
        dict with 'translation', 'source', 'likelihood', 'service_name'
        keys, or None if DeepL is unavailable / call failed.
    """
    client = _get_client()
    if client is None:
        return None

    word = (data.get("word") or "").strip()
    context = (data.get("context") or "").strip()
    source_lang = data.get("source_language") or ""
    target_lang = data.get("target_language") or ""

    if not word or not source_lang or not target_lang:
        return None

    try:
        result = client.translate_text(
            word,
            source_lang=source_lang.upper(),
            target_lang=_to_deepl_target_lang(target_lang),
            context=context or None,
        )
    except Exception as e:
        logger.warning(f"DeepL translation error: {e}")
        return None

    text = (result.text or "").strip()
    if not text:
        return None

    return {
        "translation": text,
        "source": "DeepL - with context",
        "likelihood": 92,
        "service_name": "DeepL - with context",
    }


def deepl_translate_article(title: str, markdown: str, source_language: str, target_language: str) -> Optional[dict]:
    """
    Translate a whole article with DeepL.

    The article goes in as Markdown and DeepL gets it rendered as HTML
    (tag_handling="html"), so its headings, lists and quotes come back as the
    same tags and are turned back into Markdown here.

    Returns:
        dict with 'title' and 'content' (Markdown), or None if DeepL is
        unavailable or the call failed (an unsupported language, the monthly
        quota) -- the caller then translates with an LLM.
    """
    client = _get_client()
    if client is None:
        return None

    import markdown2

    from zeeguu.core.content_cleaning.html_to_markdown import html_to_markdown

    source = source_language.upper()
    target = _to_deepl_target_lang(target_language)
    try:
        content = client.translate_text(
            markdown2.markdown(markdown), source_lang=source, target_lang=target, tag_handling="html"
        )
        translated_title = client.translate_text(title, source_lang=source, target_lang=target)
    except Exception as e:
        logger.warning(f"DeepL article translation failed ({source_language} -> {target_language}): {e}")
        return None

    content = html_to_markdown(content.text or "")
    if not content.strip():
        return None
    return {"title": (translated_title.text or "").strip(), "content": content}
