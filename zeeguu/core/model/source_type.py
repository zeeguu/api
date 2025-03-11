from zeeguu.core.model import db
from sqlalchemy.orm.exc import NoResultFound


class SourceType(db.Model):
    """
    The values are never updated, so we can cache them after being fetched the first
    time, avoiding the select.

    Maybe we could use this?
    https://docs.sqlalchemy.org/en/20/core/type_api.html#sqlalchemy.types.ExternalType.cache_ok
    """

    VIDEO = "Video"
    ARTICLE = "Article"

    ALL_TYPES = [VIDEO, ARTICLE]

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
        return f"<SourceType {self.type}>"

    @classmethod
    def find_by_id(cls, source_type_id: int):
        return cls.query.filter(cls.id == source_type_id).one()

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
