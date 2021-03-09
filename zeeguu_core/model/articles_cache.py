from sqlalchemy.orm import relationship

import zeeguu_core

from sqlalchemy import Column, Integer, String, ForeignKey

db = zeeguu_core.db


class ArticlesCache(db.Model):
    """

    The ArticlesCache is used to increase the speed of retrieving articles
    for certain content filtering configurations. The calculate_hash method
    calculates a hash, consisting of ids of the content selection, and this is
    stored with the articles that belong to this. This way the correct articles
    can be retrieved with a dramatic increase of speed.

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    from zeeguu_core.model.article import Article

    article_id = Column(Integer, ForeignKey(Article.id))
    article = relationship(Article)

    content_hash = Column(String(256))

    def __init__(self, article, hash):
        self.article = article
        self.content_hash = hash

    def __repr__(self):
        return f"<Hash {self.content_hash}>"

    @staticmethod
    def calculate_hash(user, topics, filters, searches, search_filters, user_languages):
        def _join_ids(a_list: list):
            return ",".join([str(l.id) for l in a_list])

        """

         This method is to calculate the hash with all the content filters.
         It simply adds a letter for the type of content and the sorted ids
         of all the content that has been added.
        :return:

        """

        result = "lan: "
        from zeeguu_core.model import User

        for each in user_languages:
            result += f"{each.code} " + str(User.levels_for(user, each))

        return (
            result
            + " top: "
            + _join_ids(topics)
            + " sear: "
            + _join_ids(searches)
            + " filt: "
            + _join_ids(filters)
            + " sear-filt: "
            + _join_ids(search_filters)
        )

    @classmethod
    def get_articles_for_hash(cls, hash, limit):
        try:
            result = cls.query.filter(cls.content_hash == hash).limit(limit)
            if result is None:
                return None
            return [article_id.article for article_id in result]
        except Exception as e:
            from sentry_sdk import capture_exception

            capture_exception(e)
            return None

    @classmethod
    def check_if_hash_exists(cls, hash):
        result = cls.query.filter(cls.content_hash == hash).first()
        if result is None:
            return False
        else:
            return True
