from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.db import db
import sqlalchemy

from zeeguu.core.model.bookmark import Bookmark


class VideoTitleContext(db.Model):
    """
    A context that is found in a title of an Video.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    bookmark_id = db.Column(db.Integer, db.ForeignKey(Bookmark.id), nullable=False)
    bookmark = db.relationship(Bookmark)

    video_id = db.Column(db.Integer, db.ForeignKey("video.id"))
    video = db.relationship("Video")

    def __init__(
        self,
        bookmark,
        video,
    ):
        self.bookmark = bookmark
        self.video = video

    def __repr__(self):
        return f"<VideoTitleContext v:{self.video_id}, b:{self.bookmark_id}>"

    @classmethod
    def find_by_bookmark(cls, bookmark):
        try:
            return cls.query.filter(cls.bookmark == bookmark).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(
        cls,
        session,
        bookmark,
        video,
        commit=True,
    ):
        try:
            return cls.query.filter(
                cls.bookmark == bookmark,
                cls.video == video,
            ).one()
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            new = cls(bookmark, video)
            session.add(new)
            if commit:
                session.commit()
            return new

    @classmethod
    def get_all_user_bookmarks_for_video_title(
        cls, user_id: int, video_id: int, as_json_serializable: bool = True
    ):
        from zeeguu.core.model.user_meaning import UserMeaning

        result = (
            Bookmark.query.join(VideoTitleContext)
            .join(UserMeaning)
            .filter(VideoTitleContext.video_id == video_id)
            .filter(UserMeaning.user_id == user_id)
        ).all()

        return [each.to_json(True) if as_json_serializable else each for each in result]
