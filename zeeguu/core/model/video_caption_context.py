from zeeguu.core.model.db import db
import sqlalchemy
from zeeguu.core.model.bookmark import Bookmark


class VideoCaptionContext(db.Model):
    """
    A context that is found in a caption of a Video.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    bookmark_id = db.Column(db.Integer, db.ForeignKey(Bookmark.id), nullable=False)
    bookmark = db.relationship(Bookmark)

    from zeeguu.core.model.caption import Caption

    caption_id = db.Column(db.Integer, db.ForeignKey(Caption.id))
    caption = db.relationship(Caption)

    def __init__(
        self,
        bookmark,
        caption,
    ):
        self.bookmark = bookmark
        self.caption = caption

    def __repr__(self):
        return f"<VideoCaptionContext c:{self.caption_id}, b:{self.bookmark.id}>"

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
        caption,
        commit=True,
    ):
        try:
            return cls.query.filter(
                cls.bookmark == bookmark,
                cls.caption == caption,
            ).one()
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            new = cls(
                bookmark,
                caption,
            )
            session.add(new)
            if commit:
                session.commit()
            return new

    @classmethod
    def get_all_user_bookmarks_for_caption(
        cls, user_id: int, caption_id: int, as_json_serializable: bool = True
    ):

        from zeeguu.core.model.user_word import UserWord

        result = (
            Bookmark.query.join(cls)
            .join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(cls.caption_id == caption_id)
            .filter(UserWord.user_id == user_id)
        ).all()

        return [each.to_json(True) if as_json_serializable else each for each in result]

    @classmethod
    def get_user_bookmarks_grouped_by_caption(cls, user_id: int, caption_ids):
        """Batched companion to get_all_user_bookmarks_for_caption.

        One query for many captions; returns {caption_id: [bookmark_json, ...]}.
        Avoids the N+1 of calling the single-caption helper per caption when
        rendering the whole transcript of a video.
        """
        if not caption_ids:
            return {}

        from zeeguu.core.model.user_word import UserWord

        rows = (
            Bookmark.query.join(cls)
            .join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(cls.caption_id.in_(caption_ids))
            .filter(UserWord.user_id == user_id)
            .add_columns(cls.caption_id)
            .all()
        )

        grouped = {}
        for bookmark, caption_id in rows:
            grouped.setdefault(caption_id, []).append(bookmark.to_json(True))
        return grouped
