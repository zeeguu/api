from zeeguu.core.model.db import db
from sqlalchemy.orm.exc import NoResultFound


class ContextType(db.Model):
    """
    The values are never updated, so we can cache them after being fetched the first
    time, avoiding the select.

    Maybe we could use this? https://docs.sqlalchemy.org/en/20/core/type_api.html#sqlalchemy.types.ExternalType.cache_ok
    """

    ARTICLE_FRAGMENT = "ArticleFragment"
    ARTICLE_TITLE = "ArticleTitle"
    ARTICLE_SUMMARY = "ArticleSummary"
    VIDEO_TITLE = "VideoTitle"
    VIDEO_CAPTION = "VideoCaption"
    WEB_FRAGMENT = "WebFragment"
    USER_EDITED_TEXT = "UserEditedText"
    ORPHAN_CONTEXT = "OrphanContext"

    ALL_TYPES = [
        ARTICLE_FRAGMENT,
        ARTICLE_TITLE,
        ARTICLE_SUMMARY,
        VIDEO_TITLE,
        VIDEO_CAPTION,
        WEB_FRAGMENT,
        USER_EDITED_TEXT,
        ORPHAN_CONTEXT,
    ]

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(45))

    def __init__(
        self,
        type,
    ):
        self.type = type

    def __repr__(self):
        return f"<ContextType {self.type}>"

    @classmethod
    def find_by_id(cls, context_type_id: int):
        return cls.query.filter(cls.id == context_type_id).one()

    @classmethod
    def find_by_type(cls, type: str):
        return cls.query.filter(cls.type == type).one()

    @classmethod
    def find_or_create(cls, session, type: str, commit=False):
        try:
            return cls.query.filter(cls.type == type).one()
        except NoResultFound:
            new_source_type = cls(type=type)
            session.add(new_source_type)
            if commit:
                session.commit()
            return new_source_type

    @classmethod
    def get_table_corresponding_to_type(cls, type: str):
        from zeeguu.core.model.article_fragment_context import ArticleFragmentContext
        from zeeguu.core.model.article_title_context import ArticleTitleContext
        from zeeguu.core.model.video_title_context import VideoTitleContext
        from zeeguu.core.model.video_caption_context import VideoCaptionContext

        match type:
            case cls.ARTICLE_FRAGMENT:
                return ArticleFragmentContext
            case cls.ARTICLE_TITLE:
                return ArticleTitleContext
            case cls.VIDEO_TITLE:
                return VideoTitleContext
            case cls.VIDEO_CAPTION:
                return VideoCaptionContext
            case _:
                return None
