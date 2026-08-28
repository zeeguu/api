from sqlalchemy import Column, Integer, ForeignKey, PrimaryKeyConstraint, DateTime
from sqlalchemy.orm import relationship

from zeeguu.core.model.db import db
from zeeguu.core.model.article import Article
from zeeguu.core.model.cohort import Cohort
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
    def get_cohorts_for_article(cls, article):
        """Classes this article is shared with, as {id, name}."""
        return [
            {"id": entry.cohort.id, "name": entry.cohort.name}
            for entry in cls.query.filter_by(article=article).all()
        ]

    @classmethod
    def get_articles_info_for_cohort(cls, cohort):
        """A cohort's articles, without any one user's reading state.

        Used by the teacher-facing class Texts tab: it shows the class's texts
        as the class holds them, not as the teacher personally has read them.
        """
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
    def get_cohort_names_for_article(cls, article):
        """Just the names -- enough to print a list, not to act on one.

        Two classes can share a name, and unsharing or filtering by class needs
        the id, so prefer get_cohorts_for_article for anything but display.
        Kept for the /get_cohorts_for_article endpoint, whose response shape
        deployed clients still depend on.
        """
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
