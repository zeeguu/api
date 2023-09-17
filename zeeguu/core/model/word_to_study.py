from .user import User
from .bookmark import Bookmark
from .language import Language

import zeeguu.core

from zeeguu.core.model import db


class WordToStudy(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

    bookmark_id = db.Column(db.Integer, db.ForeignKey(Bookmark.id, ondelete="CASCADE"))
    # bookmark = defined as a backref

    language_id = db.Column(db.Integer, db.ForeignKey(Language.id))

    nextDueDate = db.Column(db.DateTime)
    coolingInterval = db.Column(db.Integer)
    consecutiveCorrects = db.Column(db.Integer)

    def __init__(self, user, bookmark):
        self.user = user
        self.bookmark = bookmark
        self.language_id = bookmark.origin.language.id
        self.nextDueDate = None
        self.coolingInterval = None
        self.consecutiveCorrects = 0

    @classmethod
    def find(cls, bookmark):
        return cls.query.filter_by(bookmark_id=bookmark.id).one()
