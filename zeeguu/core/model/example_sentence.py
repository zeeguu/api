from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language
from zeeguu.core.model.user import User
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.meaning import Meaning
import sqlalchemy


class ExampleSentence(db.Model):
    """
    Stores example sentences that can be used as contexts for bookmarks.
    These can be:
    - AI-generated examples (has ai_generator_id)
    - User-uploaded examples (has user_id)
    - System template examples (neither ai_generator_id nor user_id)
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    
    # The example sentence content
    sentence = db.Column(db.Text, nullable=False)
    translation = db.Column(db.Text)  # Optional translation of the sentence
    
    # Language of the sentence
    language_id = db.Column(db.Integer, db.ForeignKey(Language.id), nullable=False)
    language = db.relationship(Language)
    
    # The meaning this example demonstrates
    meaning_id = db.Column(db.Integer, db.ForeignKey(Meaning.id), nullable=False)
    meaning = db.relationship(Meaning)
    
    # CEFR level this example is appropriate for
    cefr_level = db.Column(db.String(10))  # A1, A2, B1, B2, C1, C2
    
    # Source of the example (only one should be set)
    ai_generator_id = db.Column(db.Integer, db.ForeignKey(AIGenerator.id))
    ai_generator = db.relationship(AIGenerator)
    
    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    def __init__(
        self,
        sentence,
        language,
        meaning,
        translation=None,
        cefr_level=None,
        ai_generator=None,
        user=None,
    ):
        self.sentence = sentence
        self.language = language
        self.meaning = meaning
        self.translation = translation
        self.cefr_level = cefr_level
        self.ai_generator = ai_generator
        self.user = user

    def __repr__(self):
        source = "system"
        if self.ai_generator:
            source = f"ai:{self.ai_generator.name}"
        elif self.user:
            source = f"user:{self.user.id}"
        return f"<ExampleSentence {self.id}: {self.sentence[:50]}... ({source})>"

    @property
    def source_type(self):
        """Returns the type of source for this example"""
        if self.ai_generator_id:
            return "ai_generated"
        elif self.user_id:
            return "user_uploaded"
        else:
            return "system_template"

    @classmethod
    def find_by_id(cls, example_id):
        try:
            return cls.query.filter_by(id=example_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_by_meaning(cls, meaning, limit=None):
        """Find example sentences for a specific meaning"""
        query = cls.query.filter(cls.meaning == meaning).order_by(cls.created_at.desc())
        if limit:
            query = query.limit(limit)
        return query.all()

    @classmethod
    def create_ai_generated(
        cls,
        session,
        sentence,
        language,
        meaning,
        ai_generator,
        translation=None,
        cefr_level=None,
        commit=True,
    ):
        """Create an AI-generated example sentence"""
        # Debug logging
        from zeeguu.logging import log
        log(f"Creating ExampleSentence: sentence='{sentence}', translation='{translation}', cefr_level='{cefr_level}'")
        
        example = cls(
            sentence=sentence,
            language=language,
            meaning=meaning,
            translation=translation,
            cefr_level=cefr_level,
            ai_generator=ai_generator,
        )
        session.add(example)
        if commit:
            session.commit()
        return example

    @classmethod
    def create_user_uploaded(
        cls,
        session,
        sentence,
        language,
        meaning,
        user,
        translation=None,
        cefr_level=None,
        commit=True,
    ):
        """Create a user-uploaded example sentence"""
        example = cls(
            sentence=sentence,
            language=language,
            meaning=meaning,
            translation=translation,
            cefr_level=cefr_level,
            user=user,
        )
        session.add(example)
        if commit:
            session.commit()
        return example

    def to_json(self):
        return {
            "id": self.id,
            "sentence": self.sentence,
            "translation": self.translation,
            "language": self.language.code,
            "cefr_level": self.cefr_level,
            "source_type": self.source_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }