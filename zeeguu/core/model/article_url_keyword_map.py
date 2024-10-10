from zeeguu.core.model import db
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship


class ArticleUrlKeywordMap(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "article_url_keyword_map"

    article_id = Column(ForeignKey("article.id"), primary_key=True)
    url_keyword_id = Column(ForeignKey("url_keyword.id"), primary_key=True)
    rank = Column(Integer)
    article = relationship("Article", back_populates="url_keywords")
    url_keyword = relationship("UrlKeyword", back_populates="articles")
