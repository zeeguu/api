from zeeguu.core.model import db


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
    VIDEO_SUBTITLE = "VideoSubtitle"
    WEB_FRAGMENT = "WebFragment"
    USER_EDITED = "UserEdited"

    TYPE_ID_CACHE = {}
    ID_TYPE_CACHE = {}

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
        if id not in cls.ID_TYPE_CACHE:
            row = cls.query.filter(cls.id == context_type_id).one()
            cls.ID_TYPE_CACHE[row.id] = row
            cls.TYPE_ID_CACHE[row.type] = row
        return cls.ID_TYPE_CACHE[context_type_id]

    @classmethod
    def find_by_type(cls, type: str):
        if type not in cls.TYPE_ID_CACHE:
            row = cls.query.filter(cls.type == type).one()
            cls.ID_TYPE_CACHE[row.id] = row
            cls.TYPE_ID_CACHE[row.type] = row
        return cls.TYPE_ID_CACHE[type]

    @classmethod
    def get_table_corresponding_to_type(cls, type: str):
        from zeeguu.core.model.article_fragment_context import ArticleFragmentContext
        from zeeguu.core.model.article_title_context import ArticleTitleContext

        match type:
            case cls.ARTICLE_FRAGMENT:
                return ArticleFragmentContext
            case cls.ARTICLE_TITLE:
                return ArticleTitleContext
