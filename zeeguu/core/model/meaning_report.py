from datetime import datetime

from zeeguu.core.model import db


class MeaningReport(db.Model):
    """
    User reports for AI-generated content at the meaning level.

    Used to flag bad examples, wrong explanations, incorrect CEFR levels, etc.
    """

    __tablename__ = "meaning_report"

    id = db.Column(db.Integer, primary_key=True)
    meaning_id = db.Column(db.Integer, db.ForeignKey("meaning.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(
        db.Enum("bad_examples", "wrong_meaning", "wrong_level", "other"),
        nullable=False,
    )
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    resolved = db.Column(db.Boolean, default=False)

    meaning = db.relationship("Meaning", backref="reports")
    user = db.relationship("User")

    def __init__(self, meaning, user, reason, comment=None):
        self.meaning_id = meaning.id
        self.user_id = user.id
        self.reason = reason
        self.comment = comment

    @classmethod
    def create(cls, session, meaning, user, reason, comment=None):
        report = cls(meaning, user, reason, comment)
        session.add(report)
        session.commit()
        return report

    @classmethod
    def count_for_meaning(cls, meaning_id):
        return cls.query.filter_by(meaning_id=meaning_id, resolved=False).count()

    def as_dictionary(self):
        return {
            "id": self.id,
            "meaning_id": self.meaning_id,
            "user_id": self.user_id,
            "reason": self.reason,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved": self.resolved,
        }
