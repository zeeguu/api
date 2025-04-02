from zeeguu.core.model import db

class VideoTopicMap(db.Model):
    __tablename__ = "video_topic_map"

    video_id = db.Column(db.Integer, db.ForeignKey("video.id"))
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"))
    video = db.relationship("Video")
    topic = db.relationship("Topic")

    __table_args__ = (
        db.PrimaryKeyConstraint("video_id", "topic_id"),
        {"mysql_collate": "utf8_bin"},
    )

    def __init__(self, video, topic):
        self.video = video
        self.topic = topic
    
    def __repr__(self):
        return f"<VideoTopicMap {self.video} - {self.topic}>"
    
    def as_dictionary(self):
        return dict(
            video_id=self.video_id,
            topic_id=self.topic_id
        )