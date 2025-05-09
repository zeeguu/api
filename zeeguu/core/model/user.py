#
import datetime
import json
import random
import re

import sqlalchemy.orm
import zeeguu.core
from sqlalchemy import Column, ForeignKey, Integer, Boolean, func
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.language.difficulty_estimator_factory import DifficultyEstimatorFactory
from zeeguu.core.model.language import Language
from zeeguu.core.model.learning_cycle import LearningCycle

from zeeguu.logging import log
from zeeguu.core.util import password_hash

from zeeguu.core.model import db
from zeeguu.logging import warning

# This mapping reflects splitting
# the scale of 0 - 100 into 6 bands.
# Rounded up (16.6666 ~ 17)
CEFR_TO_DIFFICULTY_MAPPING = {
    1: (0, 1.7),
    2: (1.7, 3.4),
    3: (3.4, 5.1),
    4: (5.1, 6.8),
    5: (6.8, 8.5),
    6: (8.5, 10),
}


class User(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    EMAIL_VALIDATION_REGEX = r"(^[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+$)"
    ANONYMOUS_EMAIL_DOMAIN = "@anon.zeeguu"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    name = db.Column(db.String(255))
    invitation_code = db.Column(db.String(255))
    password = db.Column(db.String(255))
    password_salt = db.Column(db.String(255))
    learned_language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    learned_language = relationship(Language, foreign_keys=[learned_language_id])
    native_language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    native_language = relationship(Language, foreign_keys=[native_language_id])

    cohorts = relationship("UserCohortMap", back_populates="user")

    is_dev = Column(Boolean)

    def __init__(
        self,
        email,
        name,
        password,
        learned_language=None,
        native_language=None,
        invitation_code=None,
        is_dev=0,
    ):
        self.email = email
        self.name = name
        self.update_password(password)
        self.learned_language = learned_language or Language.default_learned()
        self.native_language = native_language or Language.default_native_language()
        self.invitation_code = invitation_code
        self.is_dev = is_dev

    @classmethod
    def create_anonymous(
        cls, uuid, password, learned_language_code=None, native_language_code=None
    ):
        """

        :param uuid:
        :param password:
        :param learned_language_code:
        :param native_language_code:
        :return:
        """

        # since the DB must have an email we generate a fake one
        fake_email = uuid + cls.ANONYMOUS_EMAIL_DOMAIN

        if learned_language_code is not None:
            try:
                learned_language = Language.find_or_create(learned_language_code)
            except NoResultFound as e:
                learned_language = None
        else:
            learned_language = None

        if native_language_code is not None:
            try:
                native_language = Language.find_or_create(native_language_code)
            except NoResultFound as e:
                native_language = None
        else:
            native_language = None

        new_user = cls(
            fake_email,
            uuid,
            password,
            learned_language=learned_language,
            native_language=native_language,
        )

        return new_user

    def __repr__(self):
        return "<User %r>" % (self.email)

    def is_member_of_cohort(self, cohort_id):
        cohort_id = int(cohort_id)
        return any([c.cohort_id == cohort_id for c in self.cohorts])

    def remove_from_cohort(self, cohort_id, session):
        from zeeguu.core.model.user_cohort_map import UserCohortMap

        cohort_id = int(cohort_id)
        UserCohortMap.query.filter(UserCohortMap.user_id == self.id).filter(
            UserCohortMap.cohort_id == cohort_id
        ).delete()
        session.add(self)
        session.commit()

    def details_as_dictionary(self):
        from zeeguu.core.model import UserLanguage

        result = dict(
            email=self.email,
            name=self.name,
            learned_language=self.learned_language.code,
            native_language=self.native_language.code,
            is_teacher=self.isTeacher(),
            is_student=len(self.cohorts) > 0
            and not any([c.cohort_id in [93, 459] for c in self.cohorts]),
        )

        for each in UserLanguage.query.filter_by(user=self):
            result[each.language.code + "_min"] = each.declared_level_min
            result[each.language.code + "_max"] = each.declared_level_max
            result[each.language.code + "_reading"] = each.reading_news
            result[each.language.code + "_exercises"] = each.doing_exercises
            result[each.language.code + "_cefr_level"] = each.cefr_level

        return result

    def preferred_difficulty_estimator(self):
        """
        :return: Difficulty estimator from preferences,
        otherwise the default one which is FrequencyDifficultyEstimator
        """

        from zeeguu.core.model.user_preference import UserPreference

        # Must have this import here to avoid circular dependency

        preference = (
            UserPreference.get_difficulty_estimator(self)
            or "FleschKincaidDifficultyEstimator"
        )
        log(f"Difficulty estimator for user {self.id}: {preference}")
        return preference

    def text_difficulty(self, text, language):

        estimator = DifficultyEstimatorFactory.get_difficulty_estimator(
            self.preferred_difficulty_estimator()
        )
        return estimator.estimate_difficulty(text, language, self)

    def set_native_language(self, code):
        self.native_language = Language.find(code)

    def set_learned_language(
        self, language_code: str, cefr_level: int = None, session=None
    ):
        self.learned_language = Language.find(language_code)

        from zeeguu.core.model import UserLanguage

        # disable the exercises and reading for all the other languages
        all_other_languages = (
            UserLanguage.query.filter(UserLanguage.user_id == self.id)
            .filter(UserLanguage.doing_exercises == True)
            .all()
        )
        for each in all_other_languages:
            each.doing_exercises = False
            each.reading_news = False
            if session:
                session.add(each)

        language = UserLanguage.find_or_create(session, self, self.learned_language)
        language.reading_news = True
        language.doing_exercises = True
        if cefr_level:
            language.cefr_level = cefr_level

        if session:
            session.add(language)

    def set_learned_language_level(
        self, language_code: str, cefr_level: str, session=None
    ):
        learned_language = Language.find_or_create(language_code)
        from zeeguu.core.model import UserLanguage

        language = UserLanguage.find_or_create(session, self, learned_language)
        language.cefr_level = int(cefr_level)
        if session:
            session.add(language)

    # ************************************************************************
    # -------------------------------------------------------------------------
    #                                   Bookmarks
    # -------------------------------------------------------------------------
    # ************************************************************************

    def has_bookmarks(self):
        return self.bookmark_count() > 0

    def bookmarks_to_study(self, bookmark_count=100, scheduled_only=False):
        """
        We now use a logic to sort the words, if we call this everytime
        we want similar words it might bottleneck the application.

        :param bookmark_count: If None all bookmarks are returned
        :param scheduled_only: Only use bookmarks that are scheduled
        :return:
        """
        from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

        if scheduled_only:
            to_study = BasicSRSchedule.scheduled_bookmarks_due_today(
                self, bookmark_count
            )
        else:
            to_study = BasicSRSchedule.bookmarks_to_study_prioritized(
                self, bookmark_count
            )
        return to_study if bookmark_count is None else to_study[:bookmark_count]

    def bookmarks_to_learn_not_in_pipeline(self):
        """
        :return gets all bookmarks that are going to be shown in exercises
        but haven't been scheduled yet.
        """
        from zeeguu.core.word_scheduling.basicSR.basicSR import BasicSRSchedule

        words_not_started_learning = BasicSRSchedule.bookmarks_not_scheduled(self, None)
        return words_not_started_learning

    def date_of_last_bookmark(self):
        """
        Note: assumes that there are bookmarks!
        """
        return self.bookmarks_chronologically()[0].time

    def get_new_bookmarks_to_study(self, bookmarks_count):
        from zeeguu.core.sql.queries.query_loader import load_query
        from zeeguu.core.sql.query_building import list_of_dicts_from_query
        from zeeguu.core.model.bookmark import Bookmark

        query = load_query("words_to_study")
        result = list_of_dicts_from_query(
            query,
            {
                "user_id": self.id,
                "language_id": self.learned_language.id,
                "required_count": bookmarks_count,
            },
        )
        added_bookmarks = []
        seen_bookmarks = set()
        for b in result:

            id = b["bookmark_id"]
            b = Bookmark.find(id)
            # Set the learning cycle to one (from 0)
            # This is so that when they are shown in the front-end
            # they are assumed to be set to the receptive learning cycle
            # and associated with the receptive cycle. These are not saved
            # to the DB unless an exercise is completed.
            b.learning_cycle = 1
            b_word = b.origin.word.lower()
            # Avoid the same bookmark
            if not (b_word in seen_bookmarks):
                added_bookmarks.append(b)
                seen_bookmarks.add(b_word)

        return added_bookmarks

    def liked_articles(self):
        from zeeguu.core.model.user_article import UserArticle

        return UserArticle.all_liked_articles_of_user(self)

    def active_during_recent(self, days: int = 30):
        if not self.has_bookmarks():
            return False

        import dateutil.relativedelta

        now = datetime.datetime.now()
        a_while_ago = now - dateutil.relativedelta.relativedelta(days=days)
        return self.date_of_last_bookmark() > a_while_ago

    def add_user_to_cohort(self, cohort, session):
        from zeeguu.core.model.user_cohort_map import UserCohortMap

        new_cohort = UserCohortMap(user=self, cohort=cohort)
        session.add(new_cohort)
        session.commit()

    def cohort_articles_for_user(self):
        from zeeguu.core.model import Cohort, CohortArticleMap

        all_articles = []
        try:
            for c in self.cohorts:
                cohort = Cohort.find(c.cohort_id)
                if cohort.language_id == self.learned_language_id:
                    # Only add texts on the current "learning language"
                    cohort_articles = CohortArticleMap.get_articles_info_for_cohort(
                        cohort
                    )
                    all_articles += cohort_articles
            return all_articles
        except NoResultFound as e:
            return []

    def isTeacher(self):
        from zeeguu.core.model import Teacher

        try:
            Teacher.query.filter_by(user_id=self.id).one()
            return True
        except NoResultFound:

            return False

    @classmethod
    @sqlalchemy.orm.validates("email")
    def validate_email(cls, col, email):
        if any(x.isupper() for x in email):
            raise ValueError("You should use only lowercase letters for email")
        if not re.match(cls.EMAIL_VALIDATION_REGEX, email):
            raise ValueError("Invalid email address")
        return email

    @classmethod
    @sqlalchemy.orm.validates("password")
    def validate_password(cls, col, password):
        if password is None or len(password) == 0:
            raise ValueError("Invalid password")
        return password

    @classmethod
    @sqlalchemy.orm.validates("name")
    def validate_name(cls, col, name):
        if name is None or len(name) == 0:
            raise ValueError("Invalid username")
        return name

    def update_password(self, password: str):
        """

        :param password: str
        :return:
        """
        salt_bytes = "".join(chr(random.randint(0, 255)) for _ in range(32)).encode(
            "utf-8"
        )

        self.password = password_hash(password, salt_bytes)
        self.password_salt = salt_bytes.hex()

    def all_reading_sessions(
        self,
        after_date=datetime.datetime(1970, 1, 1),
        before_date=datetime.date.today() + datetime.timedelta(days=1),
        language_id=None,
    ):
        from zeeguu.core.model.user_reading_session import UserReadingSession
        from zeeguu.core.model.article import Article

        query = zeeguu.core.model.db.session.query(UserReadingSession)
        query = query.join(Article, Article.id == UserReadingSession.article_id)
        # TODO: join with Article on language_id
        # print(language_id)

        query = query.filter(UserReadingSession.user_id == self.id)
        query = query.filter(UserReadingSession.start_time >= after_date)
        query = query.filter(UserReadingSession.start_time <= before_date)
        query = query.order_by(UserReadingSession.start_time)

        if language_id:
            query = query.filter(Article.language_id == language_id)

        all_sessions = query.all()

        return all_sessions

    def all_bookmarks(
        self,
        after_date=None,
        before_date=None,
        language_id=None,
    ):
        from zeeguu.core.model import Bookmark, UserWord

        if after_date is None:
            after_date = datetime.datetime(1970, 1, 1)
        if before_date is None:
            before_date = datetime.date.today() + datetime.timedelta(days=1)
        query = zeeguu.core.model.db.session.query(Bookmark)

        query = query.join(UserWord, Bookmark.origin_id == UserWord.id)

        if language_id == None:
            query = query.filter(UserWord.language_id == self.learned_language_id)
        else:
            query = query.filter(UserWord.language_id == language_id)

        query = query.filter(Bookmark.user_id == self.id)
        query = query.filter(Bookmark.time >= after_date)
        query = query.filter(Bookmark.time <= before_date)
        # Tempory, at some point all bookmarks should keep source
        # (It should be a meaning rather than a bookmark (for exercises))
        query = query.filter(Bookmark.source_id != None)
        query = query.order_by(Bookmark.time)

        return query.all()

    def all_bookmarks_fit_for_study(self):
        from zeeguu.core.model.bookmark import Bookmark

        query = zeeguu.core.model.db.session.query(Bookmark)
        return (query.filter_by(user_id=self.id).filter_by(fit_for_study=True)).all()

    def bookmarks_chronologically(self):
        from zeeguu.core.model.bookmark import Bookmark

        query = zeeguu.core.model.db.session.query(Bookmark)
        return (query.filter_by(user_id=self.id).order_by(Bookmark.time.desc())).all()

    def starred_bookmarks(self, count):
        from zeeguu.core.model import Bookmark, UserWord

        query = zeeguu.core.model.db.session.query(Bookmark)
        return (
            query.join(UserWord, Bookmark.origin_id == UserWord.id)
            .filter(UserWord.language_id == self.learned_language_id)
            .filter(Bookmark.user_id == self.id)
            .filter(Bookmark.starred == True)
            .order_by(Bookmark.time.desc())
            .limit(count)
        )

    def learned_bookmarks(self, count=50):
        from zeeguu.core.model import Bookmark, UserWord

        query = zeeguu.core.model.db.session.query(Bookmark)
        learned = (
            query.join(UserWord, Bookmark.origin_id == UserWord.id)
            .filter(UserWord.language_id == self.learned_language_id)
            .filter(Bookmark.user_id == self.id)
            .filter(Bookmark.learned_time != None)
            .order_by(Bookmark.learned_time.desc())
            .limit(count)
        )

        return learned

    def total_learned_bookmarks(self):
        from zeeguu.core.model import Bookmark, UserWord

        query = zeeguu.core.model.db.session.query(Bookmark)
        learned = (
            query.join(UserWord, Bookmark.origin_id == UserWord.id)
            .filter(UserWord.language_id == self.learned_language_id)
            .filter(Bookmark.user_id == self.id)
            .filter(Bookmark.learned_time != None)
            .all()
        )
        return len(learned)

    def _datetime_to_date(self, date_time):
        """
        we define datetime as being any datetime object,
        and date as being a datetime object with only the year, month and day part
        """
        return date_time.replace(
            date_time.year, date_time.month, date_time.day, 0, 0, 0, 0
        )

    def _to_date_dict(self, dict_list, date_key):
        """
        :param dict_list: a list of dictionaries
        :param date_key: the key that maps to the datetime object in the dictionary
        :return: dictionary with dates mapping to a list of dictionaries
        """
        date_dict = dict()
        for dictionary in dict_list:
            date = self._datetime_to_date(getattr(dictionary, date_key))
            date_dict.setdefault(date, []).append(dictionary)

        return date_dict

    def _group_by_date_and_serialize(self, tuple_list, key_name, to_json_func):
        """
        :param tuple_list: a list of tuples with
            1. position: date
            2. position: list of objects with 'to_json()' method
        :param key_name: the key name of the final serialized objects in the result list
        :param kargs: the list of key arguments that should be passed down to the 'to_json()' method
        :return:
        """
        result = []

        for date, object_list in tuple_list:
            serialized_objects = []
            for obj in object_list:
                serialized_objects.append(to_json_func(obj))
            date_entry = dict(
                date=date.strftime("%A, %d %B %Y"),
            )
            date_entry[key_name] = serialized_objects
            result.append(date_entry)

        return result

    def reading_sessions_by_day(
        self, after_date=datetime.datetime(2010, 1, 1), max=42, language_id=None
    ):
        """
        :param after_date: The date from which the reading sessions will be queried
        :return: a serializable list of of objects containing a date and all the reading sessions belonging to that date
        """

        reading_sessions = self.all_reading_sessions(
            after_date, language_id=language_id
        )
        date_reading_sessions_dict = self._to_date_dict(
            dict_list=reading_sessions, date_key="start_time"
        )
        sorted_date_reading_sessions_tuples = sorted(
            date_reading_sessions_dict.items(), reverse=True, key=lambda tup: tup[0]
        )

        if len(sorted_date_reading_sessions_tuples) > max:
            sorted_date_reading_sessions_tuples = sorted_date_reading_sessions_tuples[
                :max
            ]

        result = self._group_by_date_and_serialize(
            sorted_date_reading_sessions_tuples,
            key_name="reading_sessions",
            to_json_func=lambda rs: rs.to_json(),
        )

        return result

    def bookmarks_by_date(self, after_date=datetime.datetime(1970, 1, 1)):
        """
        :param after_date:
        :return: a pair of 1. a dict with date-> bookmarks and 2. a sorted list of dates
        """

        def extract_day_from_date(bookmark):
            return bookmark, bookmark.time.replace(
                bookmark.time.year, bookmark.time.month, bookmark.time.day, 0, 0, 0, 0
            )

        bookmarks = self.all_bookmarks(after_date)
        bookmarks_by_date = dict()

        for elem in map(extract_day_from_date, bookmarks):
            bookmarks_by_date.setdefault(elem[1], []).append(elem[0])

        sorted_dates = list(bookmarks_by_date.keys())
        sorted_dates.sort(reverse=True)
        return bookmarks_by_date, sorted_dates

    def bookmarks_by_day(
        self,
        after_date=None,
        max=42,
        with_title=True,
        with_context=False,
        language_id=None,
    ):
        if after_date is None:
            after_date = datetime.datetime(2010, 1, 1)

        bookmarks = self.all_bookmarks(after_date, language_id=language_id)
        date_bookmarks_dict = self._to_date_dict(dict_list=bookmarks, date_key="time")
        sorted_date_bookmarks = sorted(
            date_bookmarks_dict.items(), reverse=True, key=lambda tup: tup[0]
        )

        if len(sorted_date_bookmarks) > max:
            sorted_date_bookmarks = sorted_date_bookmarks[:max]

        result = self._group_by_date_and_serialize(
            sorted_date_bookmarks,
            "bookmarks",
            lambda bookmark: bookmark.to_json(
                with_context,
                with_title=with_title,
                with_exercise_info=True,
            ),
        )
        return result

    def bookmarks_for_article(
        self,
        article_id,
        with_exercise_info=False,
        with_title=False,
        with_tokens=False,
        good_for_study=False,
        json=True,
    ):

        from zeeguu.core.model import Bookmark, Article

        json_bookmarks = []

        query = zeeguu.core.model.db.session.query(Bookmark)
        bookmarks = (
            query.join(Article, Bookmark.source_id == Article.source_id)
            .filter(Article.id == article_id)
            .filter(Bookmark.user_id == self.id)
            .order_by(Bookmark.id.asc())
            .all()
        )

        if good_for_study:
            bookmarks = [each for each in bookmarks if each.should_be_studied()]

        # TODO: Think about doing this by default in the frontend; if there's no
        # learning cycle, we assume it's RECEPTIVE. Otherwise we have to do this
        # in muliple places
        for each in bookmarks:
            each.learning_cycle = LearningCycle.RECEPTIVE

        if not json:
            return bookmarks

        for each in bookmarks:
            json_bookmarks.append(
                each.as_dictionary(
                    with_exercise_info=with_exercise_info,
                    with_title=with_title,
                    with_context_tokenized=with_tokens,
                )
            )

        return json_bookmarks

    def bookmarks_by_url_by_date(self, n_days=365):
        bookmarks_list, dates = self.bookmarks_by_date()

        most_recent_n_days = dates[0:n_days]

        urls_by_date = {}
        texts_by_url = {}
        for date in most_recent_n_days:
            for bookmark in bookmarks_list[date]:
                urls_by_date.setdefault(date, set()).add(bookmark.text.url)
                texts_by_url.setdefault(bookmark.text.url, set()).add(bookmark.text)
        return most_recent_n_days, urls_by_date, texts_by_url

    def bookmark_counts_by_date(self):
        """returns array with added bookmark amount per each date for the last year
        this function is for the activity_graph, generates data
        """

        # compute bookmark_counts_by_date
        year = datetime.date.today().year - 1
        month = datetime.date.today().month
        bookmarks_dict, dates = self.bookmarks_by_date(
            datetime.datetime(year, month, 1)
        )

        counts = []
        for date in dates:
            the_date = date.strftime("%Y-%m-%d")
            the_count = len(bookmarks_dict[date])
            counts.append(dict(date=the_date, count=the_count))

        bookmark_counts_by_date = json.dumps(counts)
        return bookmark_counts_by_date

    def learner_stats_data(self):
        """returns array with learned and learning words count per each month for the last year
        this function is for the line_graph, generates data
        """

        # compute learner_stats_data
        from tools import compute_learner_stats

        learner_stats_data = compute_learner_stats(self)

        return learner_stats_data

    def user_words(self):
        return [b.origin.word for b in self.all_bookmarks()]

    def bookmark_count(self):
        return len(self.all_bookmarks())

    def total_exercises_completed_today(self):
        from zeeguu.core.model import Exercise
        from zeeguu.core.model.bookmark import Bookmark, bookmark_exercise_mapping
        from zeeguu.core.model import UserWord

        current_date = datetime.datetime.now().date()
        total_exercises = (
            Exercise.query.join(bookmark_exercise_mapping)
            .join(Bookmark)
            .join(User)
            .join(UserWord, UserWord.id == Bookmark.origin_id)
            .filter(User.id == self.id)
            .filter(Exercise.time >= current_date)
            .filter(Bookmark.user_id == self.id)
            .filter(UserWord.language_id == self.learned_language_id)
            .count()
        )
        return total_exercises

    def word_count(self):
        return len(self.user_words())

    def levels_for(self, language: Language):
        """

            the level that the system considers for this user

            TODO: must think better about this...

        :param language:

        :return: pair of level_min and level_max for this user

        """
        from zeeguu.core.model import UserLanguage

        lang_info = UserLanguage.with_language_id(language.id, self)

        # default values, for when there's no corresponding setting
        declared_level_min = -1
        declared_level_max = 11

        # start from user's levels if they exist
        if lang_info.declared_level_min:
            if lang_info.declared_level_min > 0:
                declared_level_min = lang_info.declared_level_min

        if lang_info.declared_level_max:
            if lang_info.declared_level_max < 10:
                declared_level_max = lang_info.declared_level_max

        if lang_info.cefr_level and lang_info.cefr_level > 0:
            declared_level_min, declared_level_max = CEFR_TO_DIFFICULTY_MAPPING[
                lang_info.cefr_level
            ]

        # ML, Sept 12, 2024
        # This is too complicated stuff for something that I don't even remmeber anybody asking for
        # The teacher overriding the difficulty levels of the student with micro granularity seems
        # like more trouble than necessary.
        # Commenting it out for now and I expect that we'll remove it eventually completely
        # # If there's cohort info, consider it
        # for cohortMap in self.cohorts:
        #     each_cohort = cohortMap.cohort
        #     if each_cohort.language and each_cohort.language == language:
        #         if each_cohort.declared_level_min:
        #             # min will be the max between the teacher's min and the student's min
        #             # this means that if the teacher says 5 is min, the student can't reduce it...
        #             # otoh, if the teacher says 5 is the min but the student wants 7 that will work
        #             declared_level_min = max(
        #                 declared_level_min, each_cohort.declared_level_min
        #             )
        #         if each_cohort.declared_level_max:
        #             # a student is limited to the upper limit of his cohort
        #             declared_level_max = min(
        #                 declared_level_max, each_cohort.declared_level_max
        #             )

        return max(declared_level_min, 0), min(declared_level_max, 10)

    def has_feature(self, feature_name):
        from zeeguu.api.endpoints.feature_toggles import is_feature_enabled_for_user

        return is_feature_enabled_for_user(feature_name, self)

    @classmethod
    def find_all(cls):
        query = zeeguu.core.model.db.session.query(User)
        return query.all()

    @classmethod
    def find(cls, email):
        query = zeeguu.core.model.db.session.query(User)
        return query.filter(func.lower(User.email) == email.lower()).one()

    @classmethod
    def email_exists(cls, email):
        query = zeeguu.core.model.db.session.query(User)
        try:
            query.filter(func.lower(User.email) == email.lower()).one()
            return True
        except sqlalchemy.orm.exc.NoResultFound:
            return False

    @classmethod
    def find_by_id(cls, id):
        return User.query.filter(User.id == id).one()

    @classmethod
    def all_recent_user_ids(cls, days=90):
        from zeeguu.core.model import UserActivityData

        sometime_ago = datetime.datetime.now() - datetime.timedelta(days=days)

        query = zeeguu.core.model.db.session.query(UserActivityData)
        recent_activities = query.filter(UserActivityData.time > sometime_ago).all()
        user_ids = set([each.user_id for each in recent_activities])
        return user_ids

    @classmethod
    def exists(cls, user):

        query = zeeguu.core.model.db.session.query(User)
        try:
            query.filter_by(email=user.email, id=user.id).one()
            return True
        except NoResultFound:
            return False

    @classmethod
    def authorize(cls, email, password):
        try:
            user = cls.find(email)
            if user.password == password_hash(
                password, bytes.fromhex(user.password_salt)
            ):
                return user
        except sqlalchemy.orm.exc.NoResultFound:
            warning(f"Login attempt with wrong email: {email}")
            return None

    @classmethod
    def authorize_anonymous(cls, uuid, password):
        email = uuid + cls.ANONYMOUS_EMAIL_DOMAIN
        return cls.authorize(email, password)

    def create_default_user_preference(self):
        from zeeguu.core.model.user_preference import UserPreference

        UserPreference.find_or_create(
            db.session, self, UserPreference.PRODUCTIVE_EXERCISES, "true"
        )
