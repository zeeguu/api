from datetime import datetime

import sqlalchemy
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import relationship
from wordstats import Word

from zeeguu.core.bookmark_quality.fit_for_study import fit_for_study
from zeeguu.core.bookmark_quality.negative_qualities import bad_quality_bookmark
from zeeguu.core.model import db, User, Meaning
from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
from zeeguu.logging import log


class UserMeaning(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

    meaning_id = db.Column(db.Integer, db.ForeignKey(Meaning.id), nullable=False)
    meaning = db.relationship(Meaning)

    fit_for_study = db.Column(db.Boolean)

    user_preference = db.Column(db.Integer)

    learned_time = db.Column(db.DateTime)

    level = db.Column(db.Integer)

    bookmarks = relationship("Bookmark", back_populates="user_meaning")

    def __init__(
        self,
        user,
        meaning,
        level: int = 0,
    ):
        self.level = level
        self.user = user
        self.meaning = meaning
        self.fit_for_study = fit_for_study(self)
        self.user_preference = UserWordExPreference.NO_PREFERENCE
        self.learned_time = None
        self.level = level

    def __repr__(self):
        return f"User Meaning: {self.user} x {self.meaning} Level: {self.level}"

    def is_learned(self):
        return self.learned_time is not None

    def get_scheduler(self):
        from zeeguu.core.word_scheduling import get_scheduler

        return get_scheduler(self.user)

    def add_new_exercise(self, exercise):
        self.exercise_log.append(exercise)

    def should_be_studied(self):
        return (self.starred or self.fit_for_study) and not self.is_learned()

    def update_fit_for_study(self, session=None):
        """
            Called when something happened to the bookmark,
             that requires it's "fit for study" status to be
              updated. Including:
              - starred / unstarred
              - exercise finished for the given bookmark
              - ...

        :param session:
        :return:
        """
        self.fit_for_study = fit_for_study(self)
        if session:
            session.add(self)

    def as_dictionary(self):
        try:
            translation_word = self.meaning.translation.content
            translation_language = self.meaning.translation.language.code
        except AttributeError as e:
            translation_word = ""
            translation_language = ""
            log(
                f"Exception caught: for some reason there was no translation for {self.id}"
            )
            print(str(e))

        word_info = Word.stats(
            self.meaning.origin.content,
            self.meaning.origin.language.code,
        )

        # Fetch the BasicSRSchedule instance associated with the current bookmark
        from zeeguu.core.word_scheduling import ONE_DAY
        from zeeguu.core.word_scheduling.basicSR.basicSR import _get_end_of_today

        try:
            scheduler = self.get_scheduler()
            schedule = scheduler.query.filter(
                scheduler.user_meaning_id == self.id
            ).one()
            cooling_interval_in_days = schedule.cooling_interval // ONE_DAY
            next_practice_time = schedule.next_practice_time
            can_update_schedule = next_practice_time <= _get_end_of_today()
            consecutive_correct_answers = schedule.consecutive_correct_answers
            is_last_in_cycle = schedule.get_max_interval() == schedule.cooling_interval

            is_about_to_be_learned = schedule.is_about_to_be_learned()

        except sqlalchemy.exc.NoResultFound:
            cooling_interval_in_days = None
            can_update_schedule = None
            consecutive_correct_answers = None
            is_last_in_cycle = None
            is_about_to_be_learned = None

        # as a transition step we can simply use the most recent
        # quality bookmark when we need url e.g. or context
        first_good_bookmark = [
            b for b in self.bookmarks if not bad_quality_bookmark(b)
        ][0]
        exercise_info_dict = dict(
            to=translation_word,
            from_lang=self.meaning.origin.language.code,
            to_lang=translation_language,
            url=first_good_bookmark.text.url(),
            origin_importance=word_info.importance,
            origin_rank=word_info.rank if word_info.rank != 100000 else "",
            article_id=(
                first_good_bookmark.text.article_id
                if first_good_bookmark.text.article_id
                else ""
            ),
            source_id=first_good_bookmark.source_id,
            fit_for_study=self.fit_for_study == 1,
            level=self.level,
            cooling_interval=cooling_interval_in_days,
            is_last_in_cycle=is_last_in_cycle,
            is_about_to_be_learned=is_about_to_be_learned,
            can_update_schedule=can_update_schedule,
            user_preference=self.user_preference,
            consecutive_correct_answers=consecutive_correct_answers,
            context_in_content=first_good_bookmark.text.in_content,
            left_ellipsis=first_good_bookmark.context.left_ellipsis,
            right_ellipsis=first_good_bookmark.context.right_ellipsis,
        )

        exercise_info_dict["from"] = self.meaning.origin.content

        result = {
            **first_good_bookmark.as_dictionary(with_context_tokenized=True),
            **exercise_info_dict,
        }

        return result

    def add_new_exercise_result(
        self,
        exercise_source,
        exercise_outcome,
        exercise_solving_speed,
        session_id: int,
        other_feedback="",
        time: datetime = None,
    ):
        if not time:
            time = datetime.now()
        from zeeguu.core.model import Exercise

        exercise = Exercise(
            exercise_outcome,
            exercise_source,
            exercise_solving_speed,
            time,
            session_id,
            self,
            other_feedback,
        )

        self.add_new_exercise(exercise)
        db.session.add(exercise)

        return exercise

    def report_exercise_outcome(
        self,
        exercise_source: str,
        exercise_outcome: str,
        solving_speed,
        session_id,
        other_feedback,
        db_session,
        time: datetime = None,
    ):
        from zeeguu.core.model import ExerciseSource

        source = ExerciseSource.find_or_create(db_session, exercise_source)
        from zeeguu.core.model import ExerciseOutcome

        outcome = ExerciseOutcome.find_or_create(db_session, exercise_outcome)

        exercise = self.add_new_exercise_result(
            source, outcome, solving_speed, session_id, other_feedback, time=time
        )
        db_session.add(exercise)

        scheduler = self.get_scheduler()
        scheduler.update(db_session, self, exercise_outcome, time)

        db_session.commit()

        # This needs to be re-thought, currently the updates are done in
        # the BasicSRSchedule.update call.
        # self.update_fit_for_study(db_session)
        # self.update_learned_status(db_session)

    @classmethod
    def find_or_create(cls, session, user, meaning):

        try:
            user_meaning = cls.query.filter_by(user=user, meaning=meaning).one()
        except NoResultFound:
            user_meaning = cls(user, meaning)
            session.add(user_meaning)
            session.commit()

        return user_meaning

    @classmethod
    def exists(cls, user, meaning):
        try:
            cls.query.filter_by(user=user, meaning=meaning).one()
            return True
        except NoResultFound:
            return False
