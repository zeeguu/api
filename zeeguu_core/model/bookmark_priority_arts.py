import zeeguu_core

from zeeguu_core.model.bookmark import Bookmark

db = zeeguu_core.db


class BookmarkPriorityARTS(db.Model):
    __tablename__ = 'bookmark_priority_arts'
    __table_args__ = {'mysql_collate': 'utf8_bin'}

    bookmark_id = db.Column(db.Integer, db.ForeignKey(Bookmark.id), primary_key=True)
    bookmark = db.relationship(Bookmark)

    priority = db.Column(db.Float)

    updated = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, bookmark, priority):
        self.bookmark = bookmark
        self.priority = priority

    @classmethod
    def find_or_create(cls, bookmark, priority):
        entry = cls.query.filter(cls.bookmark_id==bookmark.id)
        if entry.first() is not None:
            return entry.first()
        else:
            return cls(bookmark, priority)

    def __repr__(self):
        return '{}: (bookmark={}, priority={:8.2f})'.format(self.__class__.__name__, self.bookmark, self.priority)
