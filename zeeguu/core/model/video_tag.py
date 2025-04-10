from zeeguu.core.model import db

class VideoTag(db.Model):
    __tablename__ = 'video_tag'
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(512))

    def __init__(self, tag):
        self.tag = tag

    def __repr__(self):
        return f'<VideoTag {self.tag}>'

    def as_dictionary(self):
        return dict(
            id=self.id,
            tag=self.tag
       )

    @classmethod
    def find_or_create(
        cls, 
        session, 
        tag_text,
    ):
        tag = session.query(cls).filter_by(tag=tag_text).first()

        if tag:
            return tag
        
        new_tag = cls(tag_text)
        session.add(new_tag)

        try:
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        
        return new_tag