from zeeguu.core.model.db import db
import sqlalchemy
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.race_safe import find_or_create


class VideoCaptionContext(db.Model):
    """
    A context that is found in a caption of a Video.
    """

    __table_args__ = (
        # At most one context row per (bookmark, caption) — see find_or_create.
        db.UniqueConstraint(
            "bookmark_id",
            "caption_id",
            name="uq_vcc_bookmark_caption",
        ),
        {"mysql_collate": "utf8_bin"},
    )

    id = db.Column(db.Integer, primary_key=True)

    bookmark_id = db.Column(
        db.Integer, db.ForeignKey(Bookmark.id, ondelete="CASCADE"), nullable=False
    )
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
        return find_or_create(
            session,
            cls,
            dict(bookmark=bookmark, caption=caption),
            lambda: cls(bookmark, caption),
            commit=commit,
        )

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
