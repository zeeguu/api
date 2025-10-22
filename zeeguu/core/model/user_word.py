from datetime import datetime

import sqlalchemy
from sqlalchemy.exc import NoResultFound

from wordstats import Word

from zeeguu.core.bookmark_quality.fit_for_study import fit_for_study
from zeeguu.core.model import User, Meaning
from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
from zeeguu.logging import log

from zeeguu.core.model.db import db


class UserWord(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "user_word"  # Explicitly set table name for migration

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

    meaning_id = db.Column(db.Integer, db.ForeignKey(Meaning.id), nullable=False)
    meaning = db.relationship(Meaning)

    fit_for_study = db.Column(db.Boolean)

    user_preference = db.Column(db.Integer)

    learned_time = db.Column(db.DateTime)

    level = db.Column(db.Integer)

    is_user_added = db.Column(db.Boolean, default=False)

    preferred_bookmark_id = db.Column(db.Integer, db.ForeignKey("bookmark.id"))

    preferred_bookmark = db.relationship(
        "Bookmark", foreign_keys=[preferred_bookmark_id]
    )

    def __init__(
        self,
        user,
        meaning,
        level: int = 0,
        is_user_added: bool = False,
    ):
        self.level = level
        self.user = user
        self.meaning = meaning
        self.fit_for_study = fit_for_study(self)
        self.user_preference = UserWordExPreference.NO_PREFERENCE
        self.learned_time = None
        self.level = level
        self.is_user_added = is_user_added

    def __repr__(self):
        return f"User Word: {self.user} x {self.meaning} Level: {self.level}"

    def is_learned(self):
        return self.learned_time is not None

    def get_scheduler(self):
        # from zeeguu.core.word_scheduling import get_scheduler
        #
        # print(self.user)
        # return get_scheduler(self.user)
        from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import (
            FourLevelsPerWord,
        )

        return FourLevelsPerWord  # Return the class for static method calls

    def add_new_exercise(self, exercise):
        self.exercise_log.append(exercise)

    def should_be_studied(self):
        return self.fit_for_study and not self.is_learned()

    def set_unfit_for_study(self, session=None):
        from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

        self.fit_for_study = False
        BasicSRSchedule.clear_user_word_schedule(session, self)
        if session:
            session.add(self)

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
        old_fit_for_study = self.fit_for_study
        self.fit_for_study = fit_for_study(self)

        # If the word became unfit for study, clear its schedule
        if old_fit_for_study and not self.fit_for_study:
            from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

            BasicSRSchedule.clear_user_word_schedule(session, self)

        if session:
            session.add(self)

    def validate_data_integrity(self):
        """
        Validates that this UserWord is in a consistent state.
        Attempts to repair data integrity issues when possible.
        Raises ValueError only if repair is not possible.
        """
        if self.preferred_bookmark is None:
            # Try to repair by setting the first bookmark as preferred
            bookmarks = self.bookmarks()
            if len(bookmarks) > 0:
                self.preferred_bookmark = bookmarks[0]
                # Log this repair for monitoring
                from zeeguu.logging import log

                log(
                    f"WARNING: Repaired UserWord {self.id} by setting preferred_bookmark to {bookmarks[0].id}"
                )
                # Save the repair
                from zeeguu.core.model import db

                db.session.add(self)
                db.session.commit()
            else:
                # No bookmarks at all - this is a serious data integrity issue
                raise ValueError(
                    f"UserWord {self.id} has no bookmarks at all - cannot repair"
                )

    def as_dictionary(self):
        # Ensure data integrity
        self.validate_data_integrity()

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

        # Ensure the phrase rank is calculated (especially for multi-word phrases)
        self.meaning.origin.ensure_rank_is_calculated()

        # Always use the database rank (unified approach for single and multi-word phrases)
        word_rank = self.meaning.origin.rank or self.meaning.origin.IMPOSSIBLE_RANK

        # Fetch the BasicSRSchedule instance associated with the current bookmark
        from zeeguu.core.word_scheduling import ONE_DAY
        from zeeguu.core.word_scheduling.basicSR.basicSR import _get_end_of_today

        try:
            scheduler = self.get_scheduler()
            schedule = scheduler.query.filter(scheduler.user_word_id == self.id).one()
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
            next_practice_time = None

        exercise_info_dict = dict(
            to=translation_word,
            from_lang=self.meaning.origin.language.code,
            to_lang=translation_language,
            url=self.preferred_bookmark.text.url(),
            origin_rank=word_rank if word_rank != 100000 else "",
            article_id=(
                self.preferred_bookmark.text.article_id
                if self.preferred_bookmark.text.article_id
                else ""
            ),
            source_id=self.preferred_bookmark.source_id,
            fit_for_study=self.fit_for_study == 1,
            level=self.level,
            cooling_interval=cooling_interval_in_days,
            is_last_in_cycle=is_last_in_cycle,
            is_about_to_be_learned=is_about_to_be_learned,
            can_update_schedule=can_update_schedule,
            user_preference=self.user_preference,
            consecutive_correct_answers=consecutive_correct_answers,
            context_in_content=self.preferred_bookmark.text.in_content,
            left_ellipsis=self.preferred_bookmark.context.left_ellipsis,
            right_ellipsis=self.preferred_bookmark.context.right_ellipsis,
            next_practice_time=next_practice_time,
        )

        exercise_info_dict["from"] = self.meaning.origin.content

        # Determine scheduling reason and days info
        scheduling_reason = None
        days_until_practice = None

        if self.is_user_added:
            scheduling_reason = "manually_added"
        elif next_practice_time:
            from datetime import datetime
            # Use naive datetime to match next_practice_time from database
            now = datetime.now()

            # Calculate days difference
            time_diff = next_practice_time - now
            days_diff = time_diff.days

            if next_practice_time <= now:
                # Overdue or due today
                if days_diff < -1:
                    scheduling_reason = "overdue"
                    days_until_practice = abs(days_diff)
                else:
                    scheduling_reason = "due_today"
            else:
                # Future practice (early practice scenario)
                scheduling_reason = "early_practice"
                days_until_practice = days_diff

        result = {
            **self.preferred_bookmark.as_dictionary(with_context_tokenized=True),
            **exercise_info_dict,
            "user_word_id": self.id,
            "meaning_id": self.meaning_id,
            "is_user_added": (
                self.is_user_added if self.is_user_added is not None else False
            ),
            "learned_datetime": (
                self.learned_time.isoformat() if self.learned_time else None
            ),
            "phrase_type": (
                self.meaning.phrase_type.value if self.meaning.phrase_type else None
            ),
            "meaning_frequency": (
                self.meaning.frequency.value if self.meaning.frequency else None
            ),
            "scheduling_reason": scheduling_reason,
            "days_until_practice": days_until_practice,
        }

        return result

    def bookmarks(self):
        from zeeguu.core.model import Bookmark

        all = (
            Bookmark.query.join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(UserWord.id == self.id)
            .all()
        )
        return all

    def add_new_exercise_result(
        self,
        db_session,
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

        if db_session:
            db_session.add(exercise)

        return exercise

    def report_exercise_outcome(
        self,
        db_session,
        exercise_source: str,
        exercise_outcome: str,
        solving_speed,
        session_id,
        other_feedback,
        time: datetime = None,
    ):
        from zeeguu.core.model import ExerciseSource, ExerciseOutcome

        source = ExerciseSource.find_or_create(db_session, exercise_source)
        outcome = ExerciseOutcome.find_or_create(db_session, exercise_outcome)

        if not time:
            time = datetime.now()
        from zeeguu.core.model import Exercise

        exercise = Exercise(
            outcome,
            source,
            solving_speed,
            time,
            session_id,
            self,
            other_feedback,
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
    def find_or_create(cls, session, user, meaning, is_user_added=False):
        """
        Find or create a UserWord for a user and meaning.

        Since Meaning.find_or_create() already handles semantic deduplication,
        we can trust that each meaning is unique and canonical.
        """
        try:
            user_word = cls.query.filter_by(user=user, meaning=meaning).one()
            # If it exists but we're marking it as user_added, update the flag
            if is_user_added and not user_word.is_user_added:
                user_word.is_user_added = True
                session.add(user_word)
                session.commit()
        except NoResultFound:
            user_word = cls(user, meaning, is_user_added=is_user_added)
            session.add(user_word)
            session.commit()

        return user_word

    @classmethod
    def exists(cls, user, meaning):
        try:
            cls.query.filter_by(user=user, meaning=meaning).one()
            return True
        except NoResultFound:
            return False
