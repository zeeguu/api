from sqlalchemy.orm import relationship

from zeeguu_core.model.feed import db, RSSFeed
from zeeguu_core.model.user import User
import sqlalchemy


class RSSFeedRegistration(db.Model):
    __table_args__ = {'mysql_collate': 'utf8_bin'}
    __tablename__ = 'rss_feed_registration'

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = relationship(User)

    rss_feed_id = db.Column(db.Integer, db.ForeignKey(RSSFeed.id))
    rss_feed = relationship(RSSFeed)

    def __init__(self, user, feed):
        self.user = user
        self.rss_feed = feed

    def __str__(self):
        return f'RSS Feed Registration ({self.user.name}, {self.rss_feed})'

    def __repr__(self):
        return f'RSS Feed Registration ({self.user.name}, {self.rss_feed})'

    @classmethod
    def find_or_create(cls, session, user, feed):
        try:
            return (cls.query.filter(cls.user == user)
                    .filter(cls.rss_feed == feed)
                    .one())
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(user, feed)
            session.add(new)
            session.commit()
            return new

    @classmethod
    def feeds_for_user(cls, user):
        """
        would have been nicer to define a method on the User class get feeds,
        but that would pollute the user model, and it's not nice.
        :param user:
        :return:
        """
        return cls.query.filter(cls.user == user).all()

    @classmethod
    def non_subscribed_feeds(cls, user: 'User', language_code: 'str') -> '[RSSFeed]':

        already_registered = [each.rss_feed for each in cls.feeds_for_user(user)]

        all_available_for_language = RSSFeed.find_for_language_id(language_code)

        return [feed
                for feed in all_available_for_language
                if not (feed in already_registered)]

    @classmethod
    def with_id(cls, i):
        return (cls.query.filter(cls.id == i)).one()

    @classmethod
    def with_feed_id(cls, i, user):
        return (cls.query.filter(cls.rss_feed_id == i)) \
            .filter(cls.user_id == user.id).one()
