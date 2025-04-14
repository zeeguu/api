from zeeguu.core.model import db


class VideoTagMap(db.Model):
    __tablename__ = "video_tag_map"

    video_id = db.Column(db.Integer, db.ForeignKey("video.id"))
    tag_id = db.Column(db.Integer, db.ForeignKey("video_tag.id"))

    video = db.relationship("Video")
    tag = db.relationship("VideoTag")

    __table_args__ = (
        db.PrimaryKeyConstraint(video_id, tag_id),
        {"mysql_collate": "utf8_bin"},
    )

    def __init__(self, video, tag):
        self.video = video
        self.tag = tag

    def __repr__(self):
        return f"<VideoTagMap {self.video} - {self.tag}>"

    def as_dictionary(self):
        return dict(video_id=self.video_id, tag_id=self.tag_id)

    @classmethod
    def find_or_create(cls, session, video, tag):
        video_tag_map = cls.query.filter(cls.video == video and cls.tag == tag).first()
        if video_tag_map:
            return video_tag_map
        else:
            new_v_t_map = cls(video=video, tag=tag)
            session.add(new_v_t_map)
            session.commit()
            return new_v_t_map
