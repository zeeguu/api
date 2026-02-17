from datetime import datetime
from sqlalchemy import desc

from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language
from zeeguu.core.model.user import User


class TranslationSearch(db.Model):
    """
    Tracks translation searches made in the Translation Tab.
    Stores the search word and learned language (active during search).
    """

    __tablename__ = "translation_search"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship(User)

    search_word = db.Column(db.String(255), nullable=False)

    learned_language_id = db.Column(
        db.Integer, db.ForeignKey(Language.id), nullable=False
    )
    learned_language = db.relationship(Language)

    search_time = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def __init__(self, user: User, search_word: str, learned_language: Language):
        self.user = user
        self.search_word = search_word
        self.learned_language = learned_language
        self.search_time = datetime.now()

    def __repr__(self):
        return f"TranslationSearch({self.search_word}, {self.learned_language.code})"

    @classmethod
    def log_search(cls, session, user: User, search_word: str, learned_language: Language):
        """
        Log a translation search to history.

        Note: Does not commit - caller is responsible for committing.
        """
        search = cls(user=user, search_word=search_word, learned_language=learned_language)
        session.add(search)
        return search

    @classmethod
    def get_history(cls, user: User, learned_language: Language, limit: int = 50):
        """
        Get recent translation searches for a user in a specific language.
        Returns most recent searches first.
        """
        return (
            cls.query.filter(
                cls.user_id == user.id,
                cls.learned_language_id == learned_language.id
            )
            .order_by(desc(cls.search_time))
            .limit(limit)
            .all()
        )

    def as_dict(self):
        """Return dictionary representation for API response."""
        return {
            "id": self.id,
            "search_word": self.search_word,
            "language": self.learned_language.code,
            "search_time": self.search_time.isoformat(),
        }
