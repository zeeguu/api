from datetime import datetime
from sqlalchemy import desc

from zeeguu.core.model.db import db
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user import User


class TranslationSearch(db.Model):
    """
    Tracks successful translation searches made in the Translation Tab.
    Only logs searches where a translation was found (meaning exists).
    """

    __tablename__ = "translation_search"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship(User)

    meaning_id = db.Column(db.Integer, db.ForeignKey(Meaning.id), nullable=False)
    meaning = db.relationship(Meaning)

    search_time = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def __init__(self, user: User, meaning: Meaning):
        self.user = user
        self.meaning = meaning
        self.search_time = datetime.now()

    def __repr__(self):
        return f"TranslationSearch({self.meaning.origin.content})"

    @classmethod
    def log_search(cls, session, user: User, meaning: Meaning):
        """
        Log a translation search to history.

        Note: Does not commit - caller is responsible for committing.
        """
        search = cls(user=user, meaning=meaning)
        session.add(search)
        return search

    @classmethod
    def get_history(cls, user: User, limit: int = 50):
        """
        Get recent translation searches for a user.
        Returns most recent searches first.
        """
        return (
            cls.query.filter(cls.user_id == user.id)
            .order_by(desc(cls.search_time))
            .limit(limit)
            .all()
        )

    def as_dict(self):
        """Return dictionary representation for API response."""
        return {
            "id": self.id,
            "search_word": self.meaning.origin.content,
            "translation": self.meaning.translation.content,
            "from_language": self.meaning.origin.language.code,
            "to_language": self.meaning.translation.language.code,
            "meaning_id": self.meaning.id,
            "search_time": self.search_time.isoformat(),
        }
