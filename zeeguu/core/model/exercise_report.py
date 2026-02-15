from datetime import datetime

from zeeguu.core.model.db import db


class ExerciseReport(db.Model):
    """
    User reports for broken or problematic exercises.

    Used to flag issues like missing word in cloze, bad translations,
    confusing context, etc.
    """

    __tablename__ = "exercise_report"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    bookmark_id = db.Column(db.Integer, db.ForeignKey("bookmark.id"), nullable=False)
    exercise_source_id = db.Column(
        db.Integer, db.ForeignKey("exercise_source.id"), nullable=False
    )
    reason = db.Column(
        db.Enum(
            "word_not_shown",
            "wrong_highlighting",
            "context_confusing",
            "wrong_translation",
            "context_wrong",
            "other",
        ),
        nullable=False,
    )
    comment = db.Column(db.Text, nullable=True)
    context_used = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    resolved = db.Column(db.Boolean, default=False)

    user = db.relationship("User")
    bookmark = db.relationship("Bookmark", backref="exercise_reports")
    exercise_source = db.relationship("ExerciseSource")

    def __init__(
        self, user, bookmark, exercise_source, reason, comment=None, context_used=None
    ):
        self.user_id = user.id
        self.bookmark_id = bookmark.id
        self.exercise_source_id = exercise_source.id
        self.reason = reason
        self.comment = comment
        self.context_used = context_used

    @classmethod
    def create(
        cls, session, user, bookmark, exercise_source, reason, comment=None, context_used=None
    ):
        report = cls(user, bookmark, exercise_source, reason, comment, context_used)
        session.add(report)
        session.commit()
        return report

    @classmethod
    def find_by_user_bookmark_source(cls, user_id, bookmark_id, exercise_source_id):
        return cls.query.filter_by(
            user_id=user_id,
            bookmark_id=bookmark_id,
            exercise_source_id=exercise_source_id,
        ).first()

    @classmethod
    def count_for_bookmark(cls, bookmark_id):
        return cls.query.filter_by(bookmark_id=bookmark_id, resolved=False).count()

    def as_dictionary(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "bookmark_id": self.bookmark_id,
            "exercise_source_id": self.exercise_source_id,
            "reason": self.reason,
            "comment": self.comment,
            "context_used": self.context_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved": self.resolved,
        }
