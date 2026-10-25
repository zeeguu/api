import sqlalchemy

from zeeguu.core.model.db import db
from zeeguu.core.model.example_sentence import ExampleSentence


class ExampleSentenceMisfit(db.Model):
    """
    A generated example the translation validator would not pass the meaning in.

    The example was generated for the meaning, so when the two disagree it is
    the example that is wrong: the meaning stays as it is, and the example is
    not used as a context again, for any learner (see
    UserWordValidationService._try_another_sentence). A side table rather than
    a column, because few examples ever land here.
    """

    __tablename__ = "example_sentence_misfit"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_bin"}

    example_sentence_id = db.Column(
        db.Integer, db.ForeignKey(ExampleSentence.id, ondelete="CASCADE"), primary_key=True
    )
    example_sentence = db.relationship(ExampleSentence)

    # The validator's verdict and reason, e.g. "FIX: 'selv om' is the unit here"
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    @classmethod
    def mark(cls, session, example_sentence, reason):
        if session.get(cls, example_sentence.id):
            return
        # Examples are shared across learners: another validation may mark the
        # same one between our get and our insert. A savepoint keeps that
        # duplicate from failing the caller's whole transaction.
        try:
            with session.begin_nested():
                session.add(cls(example_sentence=example_sentence, reason=reason))
        except sqlalchemy.exc.IntegrityError:
            pass

    @classmethod
    def ids(cls):
        """The misfit example ids, as a subquery for `~ExampleSentence.id.in_(...)`."""
        return db.session.query(cls.example_sentence_id)
