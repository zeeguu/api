from datetime import datetime

from zeeguu.core.model.db import db


class WordReport(db.Model):
    """
    A learner's report about a word as they saw it: the meaning it had, in the
    sentence it was shown in. The kind says which part is wrong: the meaning
    (wrong_translation) or the sentence (bad_example, context_*), or the
    exercise around them.

    One table for the reports that came from exercises, the reader, and the
    word list's "bad translation" (until Oct 2026: exercise_report,
    meaning_report, and a bare skip).
    """

    __tablename__ = "word_report"

    WRONG_TRANSLATION = "wrong_translation"
    BAD_EXAMPLE = "bad_example"
    KINDS = (
        WRONG_TRANSLATION,
        BAD_EXAMPLE,
        "context_confusing",
        "word_not_shown",
        "wrong_highlighting",
        "audio_broken",
        "wrong_level",
        "other",
    )

    EXERCISE = "exercise"
    READER = "reader"
    WORD_LIST = "word_list"
    ORIGINS = (EXERCISE, READER, WORD_LIST)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    meaning_id = db.Column(
        db.Integer, db.ForeignKey("meaning.id", ondelete="CASCADE"), nullable=False
    )
    # The validator can move or orphan the user word and its bookmarks; the
    # report outlives them with the meaning and the sentence it was about.
    user_word_id = db.Column(
        db.Integer, db.ForeignKey("user_word.id", ondelete="SET NULL"), nullable=True
    )
    bookmark_id = db.Column(
        db.Integer, db.ForeignKey("bookmark.id", ondelete="SET NULL"), nullable=True
    )
    sentence = db.Column(db.Text, nullable=True)
    origin = db.Column(db.Enum(*ORIGINS), nullable=False)
    exercise_source_id = db.Column(
        db.Integer, db.ForeignKey("exercise_source.id"), nullable=True
    )
    kind = db.Column(db.Enum(*KINDS), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship("User")
    meaning = db.relationship("Meaning")
    user_word = db.relationship("UserWord")
    bookmark = db.relationship("Bookmark")
    exercise_source = db.relationship("ExerciseSource")

    @classmethod
    def create(
        cls,
        session,
        user,
        meaning,
        kind,
        origin,
        user_word=None,
        bookmark=None,
        sentence=None,
        exercise_source=None,
        comment=None,
    ):
        report = cls(
            user=user,
            meaning=meaning,
            kind=kind,
            origin=origin,
            user_word=user_word,
            bookmark=bookmark,
            sentence=sentence,
            exercise_source=exercise_source,
            comment=comment,
        )
        session.add(report)
        session.commit()
        return report

    @classmethod
    def for_bookmark(cls, session, user, bookmark, kind, origin, sentence=None, **kwargs):
        """A report on the word as shown by this bookmark, in its sentence
        (the one the client says it showed, else the bookmark's own)."""
        user_word = bookmark.user_word
        return cls.create(
            session,
            user,
            user_word.meaning,
            kind,
            origin,
            user_word=user_word,
            bookmark=bookmark,
            sentence=sentence or bookmark.get_context(),
            **kwargs,
        )

    @classmethod
    def find_exercise_report(cls, user, bookmark, exercise_source):
        return cls.query.filter_by(
            user_id=user.id,
            bookmark_id=bookmark.id,
            exercise_source_id=exercise_source.id,
        ).first()
