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
from limits import parse as parse_limit

from zeeguu.api.utils.rate_limiter import get_limiter
from zeeguu.core.model import Article, Language
from zeeguu.core.model.article_share_link import ArticleShareLink
from zeeguu.core.model.public_translation import PublicTranslation
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


def _web_url(url):
    """A real web address, not one of our own zeeguu.org placeholders
    (simplified copies get https://zeeguu.org/simplified/pending/<uuid>)."""
    if not url:
        return None
    address = url.as_string()
    return None if "zeeguu.org/" in address else address


def _is_web_content(article):
    """True for text that came from somewhere on the web: crawled from a feed,
    sent in from a browser or the phone's share sheet (article URL, or the
    upload's URL), or a copy simplified/translated from one of those.

    False for text someone typed or pasted in (teacher texts, own texts):
    those have no web address. An allowlist on purpose -- "private" can't be
    read off uploader_id: a copy simplified from an upload has no uploader
    (Article.create_simplified_version), and deleting an account clears
    uploader_id while leaving the texts in place.
    """
    for a in (article, article.parent_article):
        if a is None:
            continue
        if a.feed_id or _web_url(a.url):
            return True
        if a.source_upload and _web_url(a.source_upload.url):
            return True
    return False


# ---------------------------------------------------------------------------
@api.route("/public_article/<int:article_id>", methods=["GET"])
# ---------------------------------------------------------------------------
@cross_domain
def public_article(article_id):
    """Public, read-only article content for the shared-article page.

    Crawled articles (and their AI-simplified copies) are public content, like
    the OG preview for the same link already is. Anything else -- a text someone
    typed or pasted in, or a copy simplified from one -- only opens through a
    share link (``?s=<code>``) minted for that article. See _is_web_content.
    """
    article = Article.find_by_id(article_id)
    if not article or article.broken:
        return json_result({"error": "Article not found"}), 404

    link = ArticleShareLink.find_for_article(request.args.get("s"), article.id)
    if not _is_web_content(article) and not link:
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
@api.route("/public_translate/<int:article_id>/<to_lang_code>", methods=["POST"])
# ---------------------------------------------------------------------------
@cross_domain
def public_translate(article_id, to_lang_code):
    """Translate the word at a position in a public article. Persists nothing
    for the visitor (there is no user to own a bookmark).

    The caller sends a position, never text: {part, paragraph_i, sent_i,
    token_i, total_tokens, partner_token_i?, s?}. The server reads the word and
    its sentence from the stored article, so this can't be used as a free
    translation service for arbitrary text, and each answer is cached per
    position (PublicTranslation): repeat taps in a shared article cost nothing.
    Only cache misses count against the global daily ceiling, so someone
    draining it has to walk distinct positions in real articles.
    """
    body = request.get_json(silent=True)
    body = body if isinstance(body, dict) else {}
    position = _position_from(body)
    if position is None:
        return json_result({"error": "Bad position"}), 400

    article = Article.find_by_id(article_id)
    to_language = Language.query.filter_by(code=to_lang_code).first()
    if not article or article.broken or not to_language or to_language.id == article.language_id:
        return json_result({"error": "Not found"}), 404
    # Same gate as reading: a private text's words can't be fished out one by one.
    code = body.get("s") if isinstance(body.get("s"), str) else None
    if not _is_web_content(article) and not ArticleShareLink.find_for_article(code, article.id):
        return json_result({"error": "Not found"}), 404

    cached = PublicTranslation.find(article.id, position, to_language.id)
    if cached:
        return json_result(cached.as_response())

    located = _word_and_sentence(article, position)
    if located is None:
        return json_result({"error": "Bad position"}), 400
    word, sentence = located

    if not _charge_global_miss():
        return json_result({"error": "Too many translations today"}), 429

    if IS_DEV_SKIP_TRANSLATION:
        result = {"translation": f"T-({to_lang_code})-'{word}'", "source": "DEV_SKIP"}
    else:
        is_separated = position["partner_token_i"] >= 0
        result = get_best_translation(
            word, sentence, article.language.code, to_language.code, is_separated, sentence if is_separated else None
        )
    if not result or not result.get("translation"):
        log(f"[PUBLIC-TRANSLATE] no translation for '{word}' in article {article.id}")
        return json_result({"error": "No translation found"}), 404

    row = PublicTranslation.store(db_session, article.id, position, to_language.id, result)
    db_session.commit()
    return json_result(row.as_response())


_POSITION_FIELDS = ("paragraph_i", "sent_i", "token_i", "total_tokens")
MAX_SPAN_TOKENS = 8  # a fused phrase, never a whole sentence


def _position_from(body):
    part = body.get("part")
    if part != "title" and not (isinstance(part, int) and part > 0):
        return None
    position = {"part": str(part)}
    for field in _POSITION_FIELDS:
        value = body.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return None
        position[field] = value
    if not 1 <= position["total_tokens"] <= MAX_SPAN_TOKENS:
        return None
    partner = body.get("partner_token_i", -1)
    if partner is None:
        partner = -1
    if not isinstance(partner, int) or isinstance(partner, bool) or partner < -1:
        return None
    position["partner_token_i"] = partner
    return position


def _word_and_sentence(article, position):
    """(word text, sentence text) at a position, read from the article's own
    tokenization -- the same tokens the page was rendered from. None if the
    position doesn't exist."""
    content = article.get_tokenized_content()
    if position["part"] == "title":
        paragraphs = content.get("tokenized_title_new", {}).get("tokens", [])
    else:
        fragment_id = int(position["part"])
        fragment = next(
            (f for f in content.get("tokenized_fragments", [])
             if f["context_identifier"].get("article_fragment_id") == fragment_id),
            None,
        )
        if fragment is None:
            return None
        paragraphs = fragment["tokens"]

    sentence = [
        token
        for paragraph in paragraphs
        for sent in paragraph
        for token in sent
        if token.get("paragraph_i") == position["paragraph_i"] and token.get("sent_i") == position["sent_i"]
    ]
    if not sentence:
        return None
    by_index = {token["token_i"]: token for token in sentence}

    wanted = list(range(position["token_i"], position["token_i"] + position["total_tokens"]))
    if position["partner_token_i"] >= 0:
        wanted = sorted(set(wanted) | {position["partner_token_i"]})
    if any(i not in by_index for i in wanted):
        return None

    word = _join_tokens([by_index[i] for i in wanted]).strip(punctuation_extended + " ")
    if not word:
        return None
    return word, _join_tokens(sentence)


def _join_tokens(tokens):
    return "".join(t["text"] + (" " if t.get("has_space") else "") for t in tokens).strip()


# Only cache misses spend money, so only they count against the day's ceiling;
# once a shared article's words are cached, draining the budget is impossible
# through it. Charged by hand (not via RATE_LIMITS) because a decorator limit
# is checked before the view runs and would block cache hits too.
GLOBAL_MISS_LIMIT = parse_limit("3000 per day")


def _charge_global_miss():
    limiter = get_limiter()
    if limiter is None or not limiter.enabled:
        return True
    return limiter.limiter.hit(GLOBAL_MISS_LIMIT, "public_translate_misses")


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
