from sqlalchemy.dialects.mysql import INTEGER, BIGINT
from .db import db
from zeeguu.core.model.language import Language
from zeeguu.core.model.url import Url


class YTChannel(db.Model):
    __tablename__ = "yt_channel"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    channel_id = db.Column(db.String(512), unique=True, nullable=False)
    name = db.Column(db.String(512))
    description = db.Column(db.Text)
    views = db.Column(BIGINT(unsigned=True))
    subscribers = db.Column(INTEGER(unsigned=True))
    language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    thumbnail_url_id = db.Column(db.Integer, db.ForeignKey(Url.id))
    should_crawl = db.Column(db.Integer)
    last_crawled = db.Column(db.DateTime)

    videos = db.relationship("Video", back_populates="channel")
    language = db.relationship(Language)
    thumbnail_url = db.relationship(Url, foreign_keys="YTChannel.thumbnail_url_id")

    def __init__(
        self,
        channel_id,
        name,
        description,
        views,
        subscribers,
        language,
        thumbnail_url,
        should_crawl,
        last_crawled,
    ):
        self.channel_id = channel_id
        self.name = name
        self.description = description
        self.views = views
        self.subscribers = subscribers
        self.language = language
        self.thumbnail_url = thumbnail_url
        self.should_crawl = should_crawl
        self.last_crawled = last_crawled

    def __repr__(self):
        return f"<YTChannel {self.name} ({self.channel_id})>"

    def as_dictionary(self):
        return dict(
            id=self.id,
            channel_id=self.channel_id,
            name=self.name,
            description=self.description,
            views=self.views,
            subscribers=self.subscribers,
            language_id=self.language.id,
            thumbnail_url=(
                self.thumbnail_url.as_string() if self.thumbnail_url else None
            ),
            should_crawl=self.should_crawl,
            last_crawled=self.last_crawled,
        )

    @classmethod
    def find_or_create(
        cls,
        session,
        channel_id,
        channel_info,
        thumbnail_url,
        language,
    ):
        channel = session.query(cls).filter_by(channel_id=channel_id).first()

        if channel:
            return channel

        thumbnail_url = Url.find_or_create(session, thumbnail_url)

        new_channel = cls(
            channel_id=channel_id,
            name=channel_info["channelName"],
            description=channel_info["description"],
            views=channel_info["viewCount"],
            subscribers=channel_info["subscriberCount"],
            language=language,
            thumbnail_url=thumbnail_url,
            should_crawl=None,
            last_crawled=None,
        )
        session.add(new_channel)

        try:
            session.commit()
        except Exception as e:
            session.rollback()
            raise e

        return new_channel
