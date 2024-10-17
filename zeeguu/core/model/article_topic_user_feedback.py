from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from zeeguu.core.model.new_topic import NewTopic
from zeeguu.core.model.user import User
from zeeguu.core.model.article import Article
import sqlalchemy

from zeeguu.core.model import db


class ArticleTopicUserFeedback(db.Model):
    """
    This table allows for users to provide feedback to a specific Topic assigned to an
    article. Currently, this is only used for users to remove Inferred topics in the
    frontend. We can then have a process to review these and improve our method to
    infer topics.

    Eventually, this could be extended to support other types of feedback.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "article_topic_user_feedback"

    DO_NOT_SHOW_FEEDBACK = "DO_NOT_SHOW"

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey(Article.id))
    article = relationship(Article)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = relationship(User)

    new_topic_id = db.Column(db.Integer, db.ForeignKey(NewTopic.id))
    new_topic = relationship(NewTopic)

    feedback = db.Column(db.String(50))

    UniqueConstraint(article_id, user_id, new_topic_id)

    def __init__(self, article, user, topic, feedback):
        self.article = article
        self.user = user
        self.new_topic = topic
        self.feedback = feedback

    def __str__(self):
        return f"User New Topic Feedback ({self.user.name}, {self.new_topic}: {self.feedback})"

    __repr__ = __str__

    @classmethod
    def find_or_create(cls, session, article, user, topic, feedback):
        try:
            return (
                cls.query.filter(cls.article == article)
                .filter(cls.user == user)
                .filter(cls.new_topic == topic)
                .filter(cls.article == article)
                .filter(cls.feedback == feedback)
                .one()
            )
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(article, user, topic, feedback)
            session.add(new)
            session.commit()
            print("Commitned new row: ", new, " to article_topic_user_feedback")
            return new

    @classmethod
    def find_given_user_article(cls, article: Article, user: User):
        try:
            return cls.query.filter_by(user=user, article=article).all()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def all_for_user(cls, user):
        return cls.query.filter(cls.user == user).all()

    @classmethod
    def all_for_user_as_list_w_feedback(cls, user, feedback):
        return [
            user_feedback
            for user_feedback in cls.query.filter(cls.user == user)
            .filter(cls.feedback == feedback)
            .all()
        ]

    @classmethod
    def with_id(cls, i):
        return (cls.query.filter(cls.id == i)).one()

    @classmethod
    def with_topic_id(cls, new_topic_id, user):
        return (
            (cls.query.filter(cls.new_topic_id == new_topic_id))
            .filter(cls.user_id == user.id)
            .one()
        )
