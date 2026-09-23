"""Account-less reading of a shared article.

Someone posts a Zeeguu article link in a group chat; recipients without the app
or an account land on a public read-only page (the article analogue of the
shared audio lesson page) instead of the login screen. They can read the whole
text and tap a handful of words for a translation before being invited to sign
up. See docs/future-work/public-shared-article-page.md for the design.

Nothing here creates an identity or persists anything on the reader's behalf:
identity is deferred to the moment they log in or sign up, so a visitor who
already has an account (just not in this browser) isn't parked in a throwaway
anonymous user.
"""

import os
from string import punctuation

import flask
from flask import request

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.model import Article
from zeeguu.core.model.article_share_link import ArticleShareLink
from zeeguu.core.translation_services.translator import get_best_translation
from zeeguu.logging import log
from . import api, db_session

punctuation_extended = "»«" + punctuation
IS_DEV_SKIP_TRANSLATION = int(os.environ.get("DEV_SKIP_TRANSLATION", 0)) == 1


# ---------------------------------------------------------------------------
@api.route("/article_share_link/<int:article_id>", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
@requires_session
def article_share_link(article_id):
    """Mint (or return) the caller's public share code for this article.

    The web app appends it to the copied link as ``&s=<code>`` so the public
    page can say who shared it.
    """
    article = Article.find_by_id(article_id)
    if not article:
        return json_result({"error": "Article not found"}), 404
    link = ArticleShareLink.find_or_create(db_session, flask.g.user_id, article.id)
    db_session.commit()
    return json_result({"code": link.code})


# ---------------------------------------------------------------------------
@api.route("/public_article/<int:article_id>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
def public_article(article_id):
    """Public, read-only article content for the shared-article page.

    Crawled articles (and their AI-simplified copies) are public content, like
    the OG preview for the same link already is. A text someone *uploaded* is
    private: it only opens through a share link (``?s=<code>``) minted for it.
    """
    article = Article.find_by_id(article_id)
    if not article or article.broken:
        return json_result({"error": "Article not found"}), 404

    link = ArticleShareLink.find_for_article(request.args.get("s"), article.id)
    if article.uploader_id and not link:
        # Same answer as a missing article: don't confirm that a private id exists.
        return json_result({"error": "Article not found"}), 404

    info = article.article_info(with_content=True)
    # The reader's InteractiveText expects per-user bookmark lists; a visitor
    # has none. Uploader name is a classroom affordance, not for a public page.
    for fragment in info.get("tokenized_fragments", []):
        fragment["past_bookmarks"] = []
    if "tokenized_title_new" in info:
        info["tokenized_title_new"]["past_bookmarks"] = []
    info.pop("uploader_name", None)

    if link:
        info["shared_by_name"] = link.sharer_display_name()

    return json_result(info)


# ---------------------------------------------------------------------------
@api.route("/public_translate_word/<from_lang_code>/<to_lang_code>", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
def public_translate_word(from_lang_code, to_lang_code):
    """Translate one tapped word for an account-less reader. Persists nothing.

    The session-backed /translate_word creates a Bookmark per tap; there is no
    user to own one here. Abuse (a free public MT oracle) is capped per IP and
    globally in rate_limiter.RATE_LIMITS; the "N free words" nudge on the page
    is a separate, client-side conversion counter.
    """
    body = request.json or {}
    word_str = (body.get("word") or "").strip(punctuation_extended)
    if not word_str or len(word_str) > 100:
        return json_result({"error": "Nothing to translate"}), 400
    context = (body.get("context") or "").strip()[:1000]
    is_separated_mwe = bool(body.get("is_separated_mwe", False))
    full_sentence_context = (body.get("full_sentence_context") or None)
    if full_sentence_context:
        full_sentence_context = full_sentence_context[:1000]

    if IS_DEV_SKIP_TRANSLATION:
        result = {"translation": f"T-({to_lang_code})-'{word_str}'", "source": "DEV_SKIP"}
    else:
        result = get_best_translation(
            word_str, context, from_lang_code, to_lang_code, is_separated_mwe, full_sentence_context
        )
    if not result or not result.get("translation"):
        log(f"[PUBLIC-TRANSLATE] no translation for '{word_str}' {from_lang_code}->{to_lang_code}")
        return json_result({"error": "No translation found"}), 404

    return json_result({"translation": result["translation"], "source": result.get("source")})


# ---------------------------------------------------------------------------
@api.route("/article_share_link_info/<string:code>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
def article_share_link_info(code):
    """Who shared this link — for the logged-in reader's "shared by" credit,
    which otherwise only exists for in-app friend shares."""
    article_id = request.args.get("article_id", type=int)
    link = ArticleShareLink.find_for_article(code, article_id)
    if not link:
        return json_result({"error": "Unknown share link"}), 404
    return json_result({"shared_by_name": link.sharer_display_name()})
