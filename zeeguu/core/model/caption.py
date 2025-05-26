import sqlalchemy
from zeeguu.core.model.db import db
from zeeguu.core.model.new_text import NewText


class Caption(db.Model):
    __tablename__ = "caption"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    video = db.relationship("Video", back_populates="captions")
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"))

    # The start and end time of the caption in milliseconds
    time_start = db.Column(db.Integer)
    time_end = db.Column(db.Integer)

    text_id = db.Column(db.Integer, db.ForeignKey(NewText.id))
    text = db.relationship(NewText, foreign_keys="Caption.text_id")

    def __init__(self, video, time_start, time_end, text):
        self.video = video
        self.time_start = time_start
        self.time_end = time_end
        self.text = text

    def __repr__(self):
        return f"<Caption {self.text} ({self.time_start}-{self.time_end})>"

    def get_content(self):
        return self.text.get_content()

    def as_dictionary(self):
        return dict(
            id=self.id,
            video_id=self.video.id,
            time_start=self.time_start,
            time_end=self.time_end,
            text=self.get_content(),
        )

    @classmethod
    def create(cls, session, video, time_start, time_end, text):
        text = NewText.find_or_create(session, text, False)
        caption = cls(video, time_start, time_end, text)
        session.add(caption)
        session.commit()
        return caption

    @classmethod
    def find_by_id(cls, caption_id: int):
        return cls.query.filter_by(id=caption_id).first()
