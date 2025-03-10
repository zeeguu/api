from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship

import zeeguu.core

from zeeguu.core.model import db

class Video(db.Model):
    __tablename__ = 'video'
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.String(512), unique=True, nullable=False)
    title = db.Column(db.String(512))
    description = db.Column(db.Text)
    published_at = db.Column(db.DateTime)
    channel_id = db.Column(db.Integer, db.ForeignKey("yt_channel.id"))
    thumbnail_url = db.Column(db.String(512))
    tags = db.Column(db.Text)
    duration = db.Column(db.Integer)
    language_id = db.Column(db.Integer, db.ForeignKey("language.id"))
    vtt = db.Column(db.Text)
    plain_text = db.Column(db.Text)

    channel = db.relationship("YTChannel", back_populates="videos")
    language = db.relationship("Language")
    captions = db.relationship("Caption", back_populates="video")

    def __init__(self, video_id, title, description, published_at, channel, thumbnail_url, tags, duration, language, vtt, plain_text):
        self.video_id = video_id
        self.title = title
        self.description = description
        self.published_at = published_at
        self.channel = channel
        self.thumbnail_url = thumbnail_url
        self.tags = tags
        self.duration = duration
        self.language = language
        self.vtt = vtt
        self.plain_text = plain_text

    def __repr__(self):
        return f'<Video {self.title} ({self.video_id})>'

    def as_dictionary(self):
        return dict(
            id=self.id,
            video_id=self.video_id,
            title=self.title,
            description=self.description,
            published_at=self.published_at,
            channel=self.channel.as_dictionary(),
            thumbnail_url=self.thumbnail_url,
            tags=self.tags,
            duration=self.duration,
            language_id=self.language.id,
            vtt=self.vtt,
            plain_text=self.plain_text
        )

    @classmethod
    def find_or_create(
        cls, 
        session, 
        video_id, 
        title=None, 
        description=None, 
        published_at=None, 
        channel=None, 
        thumbnail_url=None, 
        tags=None, 
        duration=None, 
        language=None, 
        vtt=None, 
        plain_text=None
    ):
        video = session.query(cls).filter_by(video_id=video_id).first()

        if video:
            return video
        
        new_video = cls(
            video_id = video_id,
            title = title,
            description = description,
            published_at = published_at,
            channel = channel,
            thumbnail_url = thumbnail_url,
            tags = tags,
            duration = duration,
            language = language,
            vtt = vtt,
            plain_text = plain_text
        )
        session.add(new_video)

        try:
            session.commit()
        except Exception as e:
            session.rollback()
            raise e

        return new_video
