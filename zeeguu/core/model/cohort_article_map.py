from sqlalchemy import Column, Integer, ForeignKey, PrimaryKeyConstraint, DateTime, func
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.cohort import Cohort
from zeeguu.core.model.language import Language
from zeeguu.core.util.encoding import datetime_to_json


class CohortArticleMap(db.Model):

    cohort_id = Column(Integer, ForeignKey(Cohort.id))
    cohort = relationship(Cohort)

    article_id = Column(Integer, ForeignKey(Article.id))
    article = relationship(Article)
    __table_args__ = (
        PrimaryKeyConstraint(cohort_id, article_id),
        {"mysql_collate": "utf8_bin"},
    )

    published_time = Column(DateTime)

    def __init__(self, cohort, article, published_time):
        self.cohort = cohort
        self.article = article
        self.published_time = published_time

    @classmethod
    def find(cls, cohort_id, article_id):
        return cls.query.filter_by(article_id=article_id, cohort_id=cohort_id).first()

    @classmethod
    def get_articles_for_cohort(cls, cohort):
        """Returns Article objects for a cohort (not infos)."""
        return [
            relation.article
            for relation in cls.query.filter_by(cohort=cohort).all()
            if relation.article is not None
        ]

    @classmethod
    def get_cohorts_with_ids_for_article(cls, article):
        """Classes this article is shared with, as {id, name}.

        get_cohorts_for_article returns bare names, which is enough to print a
        list but not to act on one: two classes can share a name, and unsharing
        or filtering by class needs the id.
        """
        return [
            {"id": entry.cohort.id, "name": entry.cohort.name}
            for entry in cls.query.filter_by(article=article).all()
        ]

    @classmethod
    def text_counts_by_language(cls, cohort):
        """How many of this cohort's texts are in which language.

        Grouped by the *article's* language rather than the cohort's declared
        one, because that is what cohort_articles_for_user() filters on: a
        student sees a cohort text only when the article's language matches
        their learned language. The empty classroom uses this to say which
        language to switch to, so it has to count the same thing the filter
        counts.
        """
        rows = (
            db.session.query(Language, func.count(Article.id))
            .select_from(cls)
            .join(Article, Article.id == cls.article_id)
            .join(Language, Language.id == Article.language_id)
            .filter(cls.cohort_id == cohort.id)
            .group_by(Language.id)
            .all()
        )

        return [
            {"code": language.code, "name": language.name, "count": count}
            for language, count in sorted(rows, key=lambda r: -r[1])
        ]

    @classmethod
    def get_articles_info_for_cohort(cls, cohort):
        """Legacy method - returns basic article info without user context."""
        def _adapted_article_info(relation):
            article_info = relation.article.article_info()
            if relation.published_time:
                article_info["published"] = datetime_to_json(relation.published_time)
            return article_info

        articles = [
            _adapted_article_info(relation)
            for relation in cls.query.filter_by(cohort=cohort).all()
            if relation.article is not None  # Defensive check for orphaned mappings
        ]
        return sorted(articles, key=lambda x: x["metrics"]["difficulty"])

    @classmethod
    def get_cohorts_for_article(cls, article):
        cohorts = [
            cohort_article_entry.cohort.name
            for cohort_article_entry in cls.query.filter_by(article=article).all()
        ]
        return cohorts

    @classmethod
    def delete_all_for_article(cls, session, article_id):
        for each in cls.query.filter_by(article_id=article_id).all():
            session.delete(each)
        session.commit()

    @classmethod
    def delete_all_for_cohort(cls, session, cohort_id):
        for each in cls.query.filter_by(cohort_id=cohort_id).all():
            session.delete(each)
        session.commit()
