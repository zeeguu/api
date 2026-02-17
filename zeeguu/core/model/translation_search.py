from datetime import datetime
from sqlalchemy import desc

from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.user import User


class TranslationSearch(db.Model):
    """
    Tracks translation searches made in the Translation Tab.
    Used to show search history and understand user lookup patterns.
    """

    __tablename__ = "translation_search"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship(User)

    search_word = db.Column(db.String(255), nullable=False)

    search_word_language_id = db.Column(
        db.Integer, db.ForeignKey(Language.id), nullable=False
    )
    search_word_language = db.relationship(
        Language, primaryjoin=search_word_language_id == Language.id
    )

    target_language_id = db.Column(
        db.Integer, db.ForeignKey(Language.id), nullable=False
    )
    target_language = db.relationship(
        Language, primaryjoin=target_language_id == Language.id
    )

    meaning_id = db.Column(db.Integer, db.ForeignKey(Meaning.id), nullable=True)
    meaning = db.relationship(Meaning)

    search_time = db.Column(db.DateTime, nullable=False, default=datetime.now)

    def __init__(
        self,
        user: User,
        search_word: str,
        search_word_language: Language,
        target_language: Language,
        meaning: Meaning = None,
    ):
        self.user = user
        self.search_word = search_word
        self.search_word_language = search_word_language
        self.target_language = target_language
        self.meaning = meaning
        self.search_time = datetime.now()

    def __repr__(self):
        return f"TranslationSearch({self.search_word}, {self.search_word_language.code} -> {self.target_language.code})"

    @classmethod
    def log_search(
        cls,
        session,
        user: User,
        search_word: str,
        search_word_language: Language,
        target_language: Language,
        meaning: Meaning = None,
    ):
        """
        Log a translation search to history.

        Note: Does not commit - caller is responsible for committing.
        This follows the pattern of other log_* methods (ValidationLog, GrammarCorrectionLog).
        """
        search = cls(
            user=user,
            search_word=search_word,
            search_word_language=search_word_language,
            target_language=target_language,
            meaning=meaning,
        )
        session.add(search)
        return search

    @classmethod
    def get_history(cls, user: User, limit: int = 50):
        """
        Get recent translation searches for a user.
        Returns most recent searches first, with meaning details if available.
        """
        return (
            cls.query.filter(cls.user_id == user.id)
            .order_by(desc(cls.search_time))
            .limit(limit)
            .all()
        )

    def as_dict(self):
        """Return dictionary representation for API response."""
        result = {
            "id": self.id,
            "search_word": self.search_word,
            "from_language": self.search_word_language.code,
            "to_language": self.target_language.code,
            "search_time": self.search_time.isoformat(),
        }

        if self.meaning:
            result["translation"] = self.meaning.translation.content
            result["meaning_id"] = self.meaning.id

        return result
