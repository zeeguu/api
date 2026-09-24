"""Classroom rules that more than one part of the app has to agree on."""

from zeeguu.core.model.article import Article
from zeeguu.core.model.cohort_article_map import CohortArticleMap
from zeeguu.core.model.db import db


def hide_unshared_uploaded_texts(user, items):
    """Drop the uploaded texts (teachers' texts, own texts) this user may not see.

    An uploaded text reaches a student only by being shared with one of the
    classes they are in right now: leave the class, or have the teacher unshare
    it, and it disappears from the feed and search too. Crawled articles and
    anything that is not an Article (videos) pass through untouched.

    Used by the recommender and by its database fallback, so the rule holds
    whether or not Elasticsearch is up.
    """
    cohort_ids = [membership.cohort_id for membership in user.cohorts]
    shared = set()
    if cohort_ids:
        shared = {
            article_id
            for (article_id,) in db.session.query(CohortArticleMap.article_id).filter(
                CohortArticleMap.cohort_id.in_(cohort_ids)
            )
        }
    return [
        item
        for item in items
        if not (isinstance(item, Article) and item.uploader_id is not None and item.id not in shared)
    ]
