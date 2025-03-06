from datetime import datetime

import zeeguu.core
from sqlalchemy import Column, DateTime, ForeignKey, Integer, UnicodeText
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound
from zeeguu.core.model import Language
from zeeguu.core.model import db


class Plaintext(db.Model):
    """
    A plaintext is a text that has been extracted from any source.
    It can be for example a video, an article or a page fragment.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = Column(Integer, primary_key=True)

    text = Column(UnicodeText)

    language_id = Column(Integer, ForeignKey(Language.id))
    language = relationship(Language)

    fk_difficulty = Column(Integer)
    word_count = Column(Integer)

    def __init__(self, text, language: Language):
        self.text = text
        self.language_id = language.id
        self.fk_difficulty, self.word_count = self.compute_fk_and_wordcount()

    def compute_fk_and_wordcount(
        self,
    ):
        from zeeguu.core.language.difficulty_estimator_factory import (
            DifficultyEstimatorFactory,
        )
        from zeeguu.core.tokenization import TOKENIZER_MODEL, get_tokenizer
        from zeeguu.core.model.language import Language

        language = Language.find_by_id(self.language_id)
        fk_estimator = DifficultyEstimatorFactory.get_difficulty_estimator("fk")
        fk_difficulty = fk_estimator.estimate_difficulty(self.text, language, None)
        tokenizer = get_tokenizer(language, TOKENIZER_MODEL)

        # easier to store integer in the DB
        # otherwise we have to use Decimal, and it's not supported on all dbs
        fk_difficulty = fk_difficulty["grade"]
        word_count = len(tokenizer.tokenize_text(self.text))

        return fk_difficulty, word_count

    @classmethod
    def find(cls, id: int):
        """
        Retrieves a plaintext instance by its ID.

        Args:
            id (int): The ID of the plaintext to retrieve.

        Returns:
            Plaintext: The plaintext instance, or None if no result is found.
        """
        try:
            return cls.query.filter_by(id=id).order_by(cls.date.desc()).first()
        except NoResultFound:
            return None

    @classmethod
    def find_or_create(cls, session, text: str, language: Language, commit=True):
        """
        Finds an existing plaintext with the given text and language or creates a new
        one if it does not exist.

        Args:
            session: The database session to use for querying and committing data.
            text (str): The text content of the plaintext.
            language (Language): The language associated with the plaintext.
            fk_difficulty (int): The foreign key difficulty level of the plaintext.
            word_count (int): The number of words in the plaintext.

        Returns:
            Plaintext: The found or newly created plaintext instance.
        """
        try:
            return cls.query.filter_by(text=text, language_id=language.id).one()

        except NoResultFound:
            new = cls(text, language)
            session.add(new)
            if commit:
                session.commit()
            return new
