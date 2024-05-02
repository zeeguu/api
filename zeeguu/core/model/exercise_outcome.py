import sqlalchemy
import zeeguu.core

from zeeguu.core.model import db


class ExerciseOutcome(db.Model):
    __tablename__ = "exercise_outcome"
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    outcome = db.Column(db.String(255), nullable=False)
    correct = db.Column(db.Boolean, nullable=False)

    CORRECT = "C"
    TOO_EASY = "Too easy"
    SHOW_SOLUTION = "Show solution"
    RETRY = "Retry"
    WRONG = "Wrong"
    TYPO = "Typo"
    ASKED_FOR_HINT = "asked_for_hint"
    # TODO: Rename to EXERCISE_FEEDBACK
    OTHER_FEEDBACK = "other_feedback"

    correct_outcomes = [CORRECT, TOO_EASY, "Correct"]

    too_easy_outcomes = ["too_easy", TOO_EASY]

    wrong_outcomes = ["W", WRONG, SHOW_SOLUTION, ASKED_FOR_HINT]

    def __init__(self, outcome):
        self.outcome = outcome

    def __eq__(self, other):
        return self.outcome == other.outcome and self.correct == other.correct

    @property
    def correct(self):
        return self.outcome in self.correct_outcomes

    @property
    def wrong(self):
        return self.outcome in self.wrong_outcomes

    def too_easy(self):
        return self.outcome in self.too_easy_outcomes

    def free_text_feedback(self):
        """
        this can happen since the user can provide any free
        text feedback. in such a case it would probably be
        safest not to show such a bookmark until somebody
        manually verified the appropriateness of the
        feedback"""
        return (
            self.outcome not in self.correct_outcomes
            and self.outcome not in self.wrong_outcomes
            and self.outcome not in self.too_easy_outcomes
        )

    @classmethod
    def find(cls, outcome: str):
        return cls.query.filter_by(outcome=outcome).one()

    @classmethod
    def find_or_create(cls, session, _outcome: str):
        try:
            outcome = cls.find(_outcome)

        except sqlalchemy.orm.exc.NoResultFound as e:
            outcome = cls(_outcome)
        except Exception as e:
            raise e

        session.add(outcome)
        session.commit()

        return outcome
