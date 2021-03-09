import json

from sqlalchemy.orm.exc import NoResultFound

import zeeguu_core
from sqlalchemy import Column, Integer, UnicodeText

from zeeguu_core.model import User, UserWord, Language
from sys import platform


db = zeeguu_core.db

MAX_EVENT_HISTORY_LENGTH = 50

from zeeguu_core.constants import (
                        WIH_CORRECT_EX_RECOGNIZE,
                        WIH_CORRECT_EX_TRANSLATE,
                        WIH_CORRECT_EX_CHOICE,
                        WIH_CORRECT_EX_MATCH,
                        WIH_WRONG_EX_RECOGNIZE,
                        WIH_WRONG_EX_TRANSLATE,
                        WIH_WRONG_EX_CHOICE,
                        WIH_WRONG_EX_MATCH,
                        WIH_READ_CLICKED,
                        WIH_READ_NOT_CLICKED_IN_SENTENCE,
                        TIMEDELTA
)


class WordInteractionEvent(object):

    def __init__(self, event_type: int, seconds_since_epoch):
        self.event_type = event_type
        self.seconds_since_epoch = seconds_since_epoch

    def to_json(self):
        return (self.event_type, self.seconds_since_epoch)

    def __repr__(self):
        return f"(WordInteractionEvent: {self.event_type} - {self.seconds_since_epoch}) "

    @staticmethod
    def encodeExerciseResult(exercise_outcome, exercise_source):
        """
            Matches the exercise type and result to a WordHistoryEvent code

            returns: an integer representing the type of event
        """
        if exercise_outcome in [3,5]:#Correct
            if exercise_source in [1,4]: #Recognize
                return WIH_CORRECT_EX_RECOGNIZE
            elif exercise_source == 2: #Translate
                return WIH_CORRECT_EX_TRANSLATE
            elif exercise_source in [3,5,7]: #Choice
                return WIH_CORRECT_EX_CHOICE
            elif exercise_source == 6:#Match three
                return WIH_CORRECT_EX_MATCH
        elif exercise_outcome in [1,2,4]: #Wrong
            if exercise_source in [1,4]: #Recognize
                return WIH_WRONG_EX_RECOGNIZE
            elif exercise_source == 2: #Translate
                return WIH_WRONG_EX_TRANSLATE
            elif exercise_source in [3,5,7]: #Choice
                return WIH_WRONG_EX_CHOICE
            elif exercise_source == 6:#Match three
                return WIH_WRONG_EX_MATCH
        

class WordInteractionHistory(db.Model):
    __table_args__ = dict(mysql_collate='utf8_bin')
    __tablename__ = 'word_interaction_history'


    id = db.Column(Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship(User, primaryjoin=user_id == User.id)

    word_id = db.Column(db.Integer, db.ForeignKey(UserWord.id), nullable=False)
    word = db.relationship(UserWord, primaryjoin=word_id == UserWord.id)

    language = None

    # should be between 0 and 100
    known_probability = db.Column(db.Integer, db.ForeignKey(User.id))

    interaction_history = []

    # the interaction history stored as string
    interaction_history_json = db.Column(UnicodeText())

    db.UniqueConstraint(user_id, word_id)

    def __init__(self, user:User, word: UserWord):
        # never work with the self._interaction_history itself
        # always, work with the method interaction_history()
        self.user = user
        self.word = word
        self.interaction_history = []

    def insert_event(self, event_type, timestamp, timedelta = TIMEDELTA):
        """
            inserts the event in the sorted list

            add a new event, compares to previous events in order to only store most recent events

            and avoid duplicate events
        :param event_type:
        :param timestamp:
        :return:
        """

        # json can't serialize timestamps, so we simply
        if platform == "win32":
            seconds_since_epoch = int(timestamp.timestamp())
        else:
            seconds_since_epoch = int(timestamp.strftime("%s"))

        # Don't add event if it already occurs
        if self.time_exists(timestamp):
            return

        if len(self.interaction_history) == 0:
            self.interaction_history.append(WordInteractionEvent(event_type, seconds_since_epoch))

        # change event if latest event was already recorded within the timedelta
        elif self.interaction_history[-1].seconds_since_epoch + timedelta >= seconds_since_epoch and\
                (event_type == WIH_READ_CLICKED or event_type == WIH_READ_NOT_CLICKED_IN_SENTENCE):
            self.interaction_history[-1].seconds_since_epoch = seconds_since_epoch
            if event_type == WIH_READ_CLICKED:
                self.interaction_history[-1].event_type = event_type

        # append if less than 50 events recorded
        elif len(self.interaction_history) < MAX_EVENT_HISTORY_LENGTH:
            self.interaction_history.append(WordInteractionEvent(event_type, seconds_since_epoch))
            self.interaction_history.sort(key=lambda x: x.seconds_since_epoch)

        # otherwise only insert if oldest event is older than new event
        elif seconds_since_epoch > self.interaction_history[0].seconds_since_epoch:
            self.interaction_history[0] = WordInteractionEvent(event_type, seconds_since_epoch)
            self.interaction_history.sort(key=lambda x: x.seconds_since_epoch)


    def add_event(self, event_type, timestamp, timedelta = TIMEDELTA):
        """
            add a new event, no comparison or duplication check involved, use
            only if an original event is certain
            use for live implementation where time goes in one direction =)
        :param event_type:
        :param timestamp:
        :return:
        """

        # json can't serialize timestamps, so we simply
        seconds_since_epoch = int(timestamp.strftime("%s"))

        self.interaction_history.insert(0, WordInteractionEvent(event_type, seconds_since_epoch))
        self.interaction_history = self.interaction_history[0:MAX_EVENT_HISTORY_LENGTH]

        # change event if an event was already recorded within the timedelta
        if self.interaction_history[-1].seconds_since_epoch + timedelta >= seconds_since_epoch:
            self.interaction_history[-1].seconds_since_epoch = seconds_since_epoch
            if event_type == WIH_READ_CLICKED:
                self.interaction_history[-1].event_type = event_type

        # append if less than 50 events recorded
        elif len(self.interaction_history) < MAX_EVENT_HISTORY_LENGTH:
            self.interaction_history.append(WordInteractionEvent(event_type, seconds_since_epoch))

        # append new event and pop oldest event
        else:
            self.interaction_history.append(WordInteractionEvent(event_type, seconds_since_epoch))
            self.interaction_history.pop(0)



    def time_exists(self, timestamp):
        """
            Verifies if a timestamp exists in the history events

            return: True or False
        """
        if platform == "win32":
            return int(timestamp.timestamp()) in [ih.seconds_since_epoch for ih in self.interaction_history]
        else:
            return int(timestamp.strftime("%s")) in [ih.seconds_since_epoch for ih in self.interaction_history]

    def reify_interaction_history(self):
        """

            after this the interaction_history object is synced from the interaction_history_json

        :return:
        """
        list_of_tuples = json.loads(self.interaction_history_json)
        self.interaction_history = [WordInteractionEvent(pair[0], pair[1]) for pair in list_of_tuples]

    def save_to_db(self, db_session):
        """

            after this the interaction_history_json will be the result of converting  interaction_history to json
        :return:
        """
        #self.interaction_history_json = "None"
        self.interaction_history_json = json.dumps([e.to_json() for e in self.interaction_history])
        db_session.add(self)
        db_session.commit()

    @classmethod
    def find(cls, user: User, word: UserWord):
        """

            get the data from db & convert the string  rep of the history
            to the object

        :param user:
        :param word:
        :return:
        """

        try:
            history = cls.query.filter_by(user=user, word=word).one()
            history.reify_interaction_history()
            return history

        except NoResultFound:
            return None

    @classmethod
    def find_or_create(cls, user: User, word: UserWord):
        """

            get the data from db & convert the string  rep of the history
            to the object

        :param user:
        :param word:
        :return:
        """

        try:
            history = cls.query.filter_by(user=user, word=word).one()
            history.reify_interaction_history()
            return history

        except NoResultFound:
            return cls(user, word)

    @classmethod
    def find_all_word_histories_for_user(cls, user: User):
        """

            get the data from db & convert the string  rep of the history
            to the object

        :param user:
        :return:
        """

        histories = cls.query.filter_by(user=user).all()
        for history in histories:
            history.reify_interaction_history()
        return histories

    @classmethod
    def find_all_word_histories_for_user_language(cls, user: User, language: Language):
        """

            get the data from db & convert the string  rep of the history
            to the object

        :param user:
        :return:
        """

        histories = cls.query.join(UserWord).filter(cls.user == user).filter(UserWord.language == language).all()
        for history in histories:
            history.reify_interaction_history()
        return histories
