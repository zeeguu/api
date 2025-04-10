from zeeguu.core.model.bookmark_context import BookmarkContext
from zeeguu.core.model import db
import sqlalchemy

from zeeguu.core.model.bookmark import Bookmark


class VideoTitleContext(db.Model):
    """
    A context that is found in a title of an Video.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    context_id = db.Column(
        db.Integer, db.ForeignKey(BookmarkContext.id), nullable=False
    )
    context = db.relationship(BookmarkContext)

    video_id = db.Column(db.Integer, db.ForeignKey("video.id"))
    video = db.relationship("Video")

    def __init__(
        self,
        context,
        video,
    ):
        self.context = context
        self.video = video

    def __repr__(self):
        return f"<VideoTitleContext v:{self.video_id}, c:{self.context_id}>"

    @classmethod
    def find_by_context_id(cls, context_id: int):
        try:
            return cls.query.filter(cls.context_id == context_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(
        cls,
        session,
        context,
        video,
        commit=True,
    ):
        try:
            return cls.query.filter(
                cls.context == context,
                cls.video == video,
            ).one()
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            new = cls(context, video)
            session.add(new)
            if commit:
                session.commit()
            return new

    @classmethod
    def get_all_user_bookmarks_for_video_title(
        cls, user_id: int, video_id: int, as_json_serializable: bool = True
    ):
        result = (
            Bookmark.query.join(VideoTitleContext)
            .filter(VideoTitleContext.video_id == video_id)
            .filter(Bookmark.user_id == user_id)
        ).all()

        return [each.to_json(True) if as_json_serializable else each for each in result]
    
    @classmethod
    def find_by_bookmark(cls, bookmark):
        try:
            return cls.query.filter(cls.bookmark == bookmark).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None