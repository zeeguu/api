import hashlib

from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language
from zeeguu.core.util.time import server_now


class SelectionExplanation(db.Model):
    """
    A cached AI explanation of one selection as used in one sentence.

    Worth caching because the explanation is generated at temperature 0 from
    nothing but (selection, sentence, languages, level): the same inputs give
    the same text, so one learner's lookup can serve the next. Sentences are
    shared -- every reader of an article meets the same ones -- so the hit rate
    on a popular article is high, and each hit saves a Sonnet call and the
    second the learner would have spent watching a spinner.

    The sentence is keyed by hash rather than stored whole in the index: article
    sentences run long, and MySQL's index width would not take them. The full
    context is kept in a column anyway, so a cache entry can be read and judged
    by a human later.

    Not keyed by user on purpose. There is nothing personal in the inputs -- a
    word and a published sentence -- and keying by user would throw away most of
    the benefit.
    """

    __tablename__ = "selection_explanation"

    id = db.Column(db.Integer, primary_key=True)

    # The exact string the learner selected: one word, or several.
    selection = db.Column(db.String(255), nullable=False)

    # sha256 of the sentence, which is what the unique key can actually index.
    context_hash = db.Column(db.String(64), nullable=False)

    # ... and the sentence itself, so the row stays legible to a person.
    context = db.Column(db.Text, nullable=False)

    language_id = db.Column(db.Integer, db.ForeignKey(Language.id), nullable=False)
    language = db.relationship(Language, foreign_keys=[language_id])

    native_language_id = db.Column(
        db.Integer, db.ForeignKey(Language.id), nullable=False
    )
    native_language = db.relationship(Language, foreign_keys=[native_language_id])

    # An A1 and a C1 learner asked about the same word get different prose, so
    # the level is part of the key rather than a detail of the request.
    cefr_level = db.Column(db.String(2), nullable=False)

    explanation = db.Column(db.Text, nullable=False)

    created = db.Column(db.DateTime, nullable=False, default=server_now)

    __table_args__ = (
        db.UniqueConstraint(
            "selection",
            "context_hash",
            "language_id",
            "native_language_id",
            "cefr_level",
            name="unique_selection_explanation",
        ),
    )

    def __init__(
        self,
        selection,
        context,
        language,
        native_language,
        cefr_level,
        explanation,
    ):
        self.selection = selection
        self.context = context
        self.context_hash = self.hash_of(context)
        self.language = language
        self.native_language = native_language
        self.cefr_level = cefr_level
        self.explanation = explanation
        self.created = server_now()

    def __repr__(self):
        return f"<SelectionExplanation {self.selection} ({self.language.code})>"

    @classmethod
    def hash_of(cls, context: str) -> str:
        return hashlib.sha256(context.encode("utf-8")).hexdigest()

    @classmethod
    def find(cls, selection, context, language, native_language, cefr_level):
        """The cached explanation, or None."""
        return cls.query.filter_by(
            selection=selection,
            context_hash=cls.hash_of(context),
            language_id=language.id,
            native_language_id=native_language.id,
            cefr_level=cefr_level,
        ).first()

    @classmethod
    def find_or_create(
        cls, session, selection, context, language, native_language, cefr_level
    ):
        """The cached explanation, or a freshly generated and stored one.

        Returns (explanation_text, was_cached) -- the caller reports which,
        because "this came from a cache" is the sort of thing worth seeing in
        the logs when a prompt changes and the old text keeps appearing.
        """
        cached = cls.find(selection, context, language, native_language, cefr_level)
        if cached:
            return cached.explanation, True

        from zeeguu.core.llm_services.llm_service import explain_selection

        explanation = explain_selection(
            selection=selection,
            context=context,
            language=language.name,
            native_language=native_language.name,
            cefr_level=cefr_level,
        )

        row = cls(
            selection, context, language, native_language, cefr_level, explanation
        )
        session.add(row)
        session.commit()

        return explanation, False
