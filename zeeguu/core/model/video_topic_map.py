from zeeguu.core.model import db


class VideoTopicMap(db.Model):
    __tablename__ = "video_topic_map"

    video_id = db.Column(db.Integer, db.ForeignKey("video.id"))
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"))
    origin_type = db.Column(db.Integer)
    video = db.relationship("Video")
    topic = db.relationship("Topic")

    __table_args__ = (
        db.PrimaryKeyConstraint("video_id", "topic_id"),
        {"mysql_collate": "utf8_bin"},
    )

    def __init__(self, video, topic, origin_type):
        self.video = video
        self.topic = topic
        self.origin_type = origin_type

    def __repr__(self):
        return f"<VideoTopicMap {self.video} - {self.topic} (type: {self.origin_type})>"

    def as_dictionary(self):
        return {
            "video_id": self.video_id,
            "topic_id": self.topic_id,
            "origin_type": self.origin_type,
        }
