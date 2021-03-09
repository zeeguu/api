import sqlalchemy.orm

import zeeguu_core
from zeeguu_core.model.ranked_word import WordForm
from zeeguu_core.model.user import User

db = zeeguu_core.db


class EncounterStats(db.Model):
    """
    This class updates the encounters of a user
    with a given WordForm in a given target Language
    """

    __tablename__ = 'encounter_stats'
    __table_args__ = {'mysql_collate': 'utf8_bin'}

    # Assume that they learner does not know the prob of this word
    DEFAULT_PROBABILITY = 0.01

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable = False)
    user = db.relationship(User)

    word_form_id = db.Column(db.Integer, db.ForeignKey("word_form.id"), nullable=False)
    word_form = db.relationship(WordForm)

    not_looked_up_counter = db.Column(db.Integer,nullable = False)

    probability = db.Column(db.DECIMAL(10,9), nullable = False)

    db.UniqueConstraint(user_id, word_form_id)
    db.CheckConstraint('probability>=0', 'probability<=1')

    def __init__(self, user, word_form):
        """
        :param user: User
        :param word_form: WordForm
        :param not_looked_up_counter: int
        :param probability: int
        """

        self.user = user
        self.word_form = word_form
        self.not_looked_up_counter = 1

        # TODO: default probability should be taken from the wordstats module
        self.probability = EncounterStats.DEFAULT_PROBABILITY

    def event_seen_but_not_looked_up(self):
        self.not_looked_up_counter += 1

        if float(self.probability) != 1.0:
            self.probability = float(self.probability) + 0.1

    def event_looked_up(self):
        """
        Ooops. The user has looked up this word.
        Must decrease the probability that they know it
        :return:
        """
        self.probability /= 2

    @classmethod
    def find_all(cls, user, language_code):
        return cls.query.filter_by(
            user = user). \
            join(WordForm). \
            filter(WordForm.id == cls.word_form_id). \
            filter(WordForm.language_id == language_code).\
            all()

    @classmethod
    def find_or_create_wordstring(cls, user, word, language):
        word_form = WordForm.find(word, language)
        return cls.find_or_create_wordform(user, word_form)

    @classmethod
    def find_or_create_wordform(cls, user, word_form):
        """
        :param user:
        :param word_form: WordForm
        :param default_probability:
        :return:
        """
        try:
            return cls.query.filter_by(
                user = user,
                word_form = word_form
            ).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return cls(user, word_form)
