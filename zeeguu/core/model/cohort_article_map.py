from sqlalchemy import Column, Integer, ForeignKey, PrimaryKeyConstraint, DateTime
from sqlalchemy.orm import relationship

from zeeguu.core.model import db
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
    def get_articles_info_for_cohort(cls, cohort):
        def _adapted_article_info(relation):
            article_info = relation.article.article_info()
            if relation.published_time:
                article_info["published"] = datetime_to_json(relation.published_time)
            return article_info

        articles = [
            _adapted_article_info(relation)
            for relation in cls.query.filter_by(cohort=cohort).all()
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
