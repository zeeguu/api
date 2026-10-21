"""
Control characters inside an attribute value made newspaper's parse() raise
"All strings must be XML compatible", so /parse_url returned a 500 for a page
that was otherwise readable (FMD alert, 20 Oct 2026).
"""

import newspaper
import pytest

from zeeguu.core.content_retriever.parse_with_readability_server import (
    remove_xml_incompatible_chars,
)

BODY = "<p>" + "A sentence that is long enough to count as text. " * 20 + "</p>"
# \x0b (vertical tab) in a div's class attribute is enough to crash parse()
HTML_WITH_CONTROL_CHAR = (
    f'<html><body><div class="intro\x0bbox">{BODY}</div></body></html>'
)


def _parse(html):
    article = newspaper.Article(url="https://example.com/a")
    article.set_html(html)
    article.parse()
    return article


def test_removes_null_and_control_characters():
    assert remove_xml_incompatible_chars("a\x00b\x0bc\x1fd￾e") == "abcde"


def test_keeps_tab_newline_and_carriage_return():
    assert remove_xml_incompatible_chars("a\tb\nc\rd") == "a\tb\nc\rd"


def test_keeps_ordinary_unicode():
    text = "Æblegrød – «citat» 日本語 😀"
    assert remove_xml_incompatible_chars(text) == text


def test_control_char_in_attribute_crashes_newspaper_parse():
    # Documents why the cleanup exists: without it, parse() raises.
    with pytest.raises(ValueError, match="XML compatible"):
        _parse(HTML_WITH_CONTROL_CHAR)


def test_cleaned_html_parses_and_keeps_the_text():
    article = _parse(remove_xml_incompatible_chars(HTML_WITH_CONTROL_CHAR))
    assert "A sentence that is long enough" in article.text
