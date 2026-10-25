"""
Saving a translated article, shared by the two translate-and-adapt endpoints
(POST /translate_and_adapt_article and
POST /article_upload/<id>/translate_and_adapt).
"""

from zeeguu.core.model import Article
from zeeguu.core.model.race_safe import find_or_create_and_report


def save_translated_article(db_session, translated_url, make):
    """
    Insert the article built by `make()` at `translated_url` with its
    fragments, and commit. Returns the article.

    A second request for the same translation (double tap, retry) can miss
    the endpoint's existing-article lookup while the first one waits on the
    LLM. Both then insert at this url; the loser gets the winner's article
    back.

    `make` must not commit: it runs inside the helper's savepoint. Resolve
    anything that commits (e.g. Url.find_or_create) before calling this.
    """
    if translated_url is None:
        # Url.find_or_create gives None when the path is over 255 chars, and
        # the "#translated-from-..." suffix can push a url over. With no url
        # to key on, the helper would look up `url_id IS NULL` and find
        # unrelated articles; insert directly, without race protection.
        article, created = make(), True
        db_session.add(article)
    else:
        article, created = find_or_create_and_report(
            db_session, Article, dict(url=translated_url), make
        )
    # Fragments only for an article this request created: the loser must not
    # add a second set to the winner's. One commit for article and fragments,
    # so whoever sees the article sees its fragments too. For the loser the
    # commit also ends its REPEATABLE READ snapshot, which predates the
    # winner's commit and would show the article without fragments.
    if created:
        article.create_article_fragments(db_session)
    db_session.commit()
    return article
