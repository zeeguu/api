import sqlalchemy
import zeeguu.core

from zeeguu.core.model.db import db


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
    CORRECT_AFTER_HINT = "HC"

    too_easy_outcomes = ["too_easy", TOO_EASY]

    wrong_outcomes = ["W", WRONG, SHOW_SOLUTION, ASKED_FOR_HINT]

    correct_after_translation = ["TC", "TTC", "TTTC"]

    # The one definition of "correct": solved on the first try, unaided.
    # A hint (HC) or looking up the translation first (TC, TTC, ...) is not
    # correct. "Correct" is the pre-2021 spelling of "C".
    correct_outcomes = [CORRECT, "Correct"]

    @classmethod
    def is_valid_attempt(cls, outcome: str):
        """
        The user might have multiple attempts:
            e.g. "WWWHHC",
                 "WWTTHC"...
        By checking if the characters in the answer are part
        of the set of possible reports of the exercise, we can
        conclude it is a user attempt.
        """
        allowed_attempts = set(["C", "W", "T", "S", "H"])
        return allowed_attempts.issuperset(set([c for c in outcome]))

    @classmethod
    def is_correct(cls, outcome: str):
        return outcome in cls.correct_outcomes

    def __init__(self, outcome):
        self.outcome = outcome

    def __eq__(self, other):
        return self.outcome == other.outcome and self.correct == other.correct

    @property
    def correct(self):
        return ExerciseOutcome.is_correct(self.outcome)

    @property
    def wrong(self):
        return self.outcome in self.wrong_outcomes

    def too_easy(self):
        return self.outcome in self.too_easy_outcomes

    def free_text_feedback(self):
        result = (
            self.outcome not in self.correct_outcomes
            and self.outcome not in self.wrong_outcomes
            and self.outcome not in self.too_easy_outcomes
            and not ExerciseOutcome.is_valid_attempt(self.outcome)
        )
        return result

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
