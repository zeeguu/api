import re
from datetime import datetime, time

import sqlalchemy
from sqlalchemy import Column, String
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model.db import db
from zeeguu.core.model.user import User
from zeeguu.logging import log


class UserPreference(db.Model):
    """
    All preferences are saved in the DB as user_id - key - value triples.
    Where the key and value are both Strings.

    To avoid working with hardcoded strings add the constant for the keys
    in this class, like DIFFICULTY_ESTIMATOR for example.

    Better yet, add also corresponding set and get methods, like:
        set_difficulty_estimator
        get_difficulty_estimator

    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

    key = Column(String(255), nullable=True)
    value = Column(String(255), nullable=True)

    # Key Names Below
    DIFFICULTY_ESTIMATOR = "difficulty_estimator"
    AUDIO_EXERCISES = "audio_exercises"
    PRODUCTIVE_EXERCISES = "productive_exercises"
    TRANSLATE_IN_READER = "translate_reader"
    PRONOUNCE_IN_READER = "pronounce_reader"
    MAX_WORDS_TO_SCHEDULE = "max_words_to_schedule"
    FILTER_DISTURBING_CONTENT = "filter_disturbing_content"  # Filter violence/death/tragedy articles
    SHOW_EASIER_ARTICLES = "show_easier_articles"  # Also show articles below the user's CEFR level
    SHOW_MWE_HINTS = "show_mwe_hints"  # Show hints for multi-word expressions
    SHOW_READING_TIMER = "show_reading_timer"  # Show timer in reader and exercises
    EMAIL_ON_ARTICLE_SHARED = "email_on_article_shared"  # Email me when a friend shares an article
    # How practice slots are given out (word_scheduling/basicSR/frequency_slots.py).
    # Both fill a free slot with the most frequent waiting word; they differ
    # in whether a slot, once given, is kept.
    WORD_SCHEDULING_STRATEGY = "word_scheduling_strategy"
    # a word keeps its slot until it is learned
    FIRST_COME = "first_come"
    # a more frequent waiting word takes the slot of a rarer word below level 2
    FREQUENCY_PRIORITY = "frequency_priority"
    WORD_SCHEDULING_STRATEGIES = (FIRST_COME, FREQUENCY_PRIORITY)
    # Unset means FREQUENCY_PRIORITY for accounts created from this day on, and
    # FIRST_COME for older ones: nobody's practice changed without their asking.
    FREQUENCY_PRIORITY_DEFAULT_FROM = datetime(2026, 11, 26)

    # Minutes of study a day that count the day for the streak, counted in each
    # language separately; Aiki mode and the study reminder (on the phone) read
    # the same number. ADR 046. Unset means the default: learners from before
    # the goal existed were given 2, the old fixed streak minimum, so no streak
    # broke when it shipped (migration 26-11-09).
    DAILY_GOAL_MINUTES = "daily_goal_minutes"
    # What a learner picks. 2 is only the grandfathered value of learners from
    # before the goal existed: still valid, but it does not count as chosen.
    DAILY_GOAL_PICKER_CHOICES = (5, 10, 15, 20)
    DAILY_GOAL_CHOICES = (2,) + DAILY_GOAL_PICKER_CHOICES
    DEFAULT_DAILY_GOAL_MINUTES = 5
    # Derived in all_for_user, not stored: whether the learner picked a goal.
    # Aiki mode and the study reminder need one (ADR 046).
    DAILY_GOAL_SET = "daily_goal_set"

    # The daily study reminder (ADR 046) is scheduled on the phone, which keeps
    # its own copy of the setting; these copies are what the server knows, so
    # it can tell which days a reminder would have fired (enabled, a time, the
    # goal not met by then, notifications allowed). Written by the app.
    STUDY_REMINDER_ENABLED = "study_reminder_enabled"  # "true" | "false"
    STUDY_REMINDER_TIME = "study_reminder_time"  # "HH:MM", the learner's local time
    # Whether the phone lets the app show notifications at all, as the OS last
    # told the app: iOS and Android settings can turn them off behind its back.
    NOTIFICATIONS_PERMISSION = "notifications_permission"
    NOTIFICATIONS_PERMISSIONS = ("granted", "denied", "prompt")
    STUDY_REMINDER_KEYS = (STUDY_REMINDER_ENABLED, STUDY_REMINDER_TIME, NOTIFICATIONS_PERMISSION)

    # Which character the learner plays in situation lessons: "man" or "woman".
    # Asked, never inferred -- not from the name either: a wrong guess would
    # address them, and in many languages drill their own sentences, in the
    # wrong gender every day. "either" (alternate) is no longer offered (Nov
    # 2026): in French or Bulgarian it had a learner say "content" one day and
    # "contente" the next. Apps already installed still send it, so it is
    # accepted and read as unset: the lessons then keep the latest lesson's
    # character (DailyLessonGenerator).
    AUDIO_LESSON_CHARACTER = "audio_lesson_character"
    AUDIO_LESSON_CHARACTERS = ("man", "woman", "either")

    # How long the learner wants their A0 audio lessons, in minutes, one of
    # lesson_tuning.LESSON_MINUTES_CHOICES. Set on the slider, or moved a step
    # by "too short" / "too long" after a lesson. Unset: their daily goal, but
    # not under 10 minutes (lesson_tuning.default_lesson_minutes).
    AUDIO_LESSON_MINUTES = "audio_lesson_minutes"

    # Daily audio lesson preferences. Keyed PER learned-language because the daily
    # lesson is stored/queried per user.learned_language; the language code is
    # appended to the prefix (e.g. "daily_audio_lesson_type_da"). A user can keep a
    # different daily topic for each language they learn.
    DAILY_AUDIO_LESSON_TYPE_PREFIX = "daily_audio_lesson_type_"  # value: three_words_lesson | topic | situation
    DAILY_AUDIO_LESSON_SUGGESTION_PREFIX = "daily_audio_lesson_suggestion_"  # value: the verbatim subject the user typed

    def __init__(self, user: User, key=None, value=None):
        self.user = user
        self.key = key
        self.value = value

    def set(self, value: str):
        self.key = value

    def get(self):
        return self.value

    def __str__(self):
        return (
            f'Preferences (uid: {self.user_id}, key:"{self.key}", value:"{self.value}")'
        )

    # Preference Specific Getter/Setter Methods
    # --------------------------------------

    @classmethod
    def get_difficulty_estimator(cls, user: User):
        return cls.get(user, cls.DIFFICULTY_ESTIMATOR)

    @classmethod
    def set_difficulty_estimator(cls, session, user: User, key: value):
        return cls.set(session, user, cls.DIFFICULTY_ESTIMATOR, key)

    @classmethod
    def validate_max_words_to_schedule(cls, value):
        """
        Validates and caps the max_words_to_schedule value.
        Returns a valid integer between 1 and MAX_WORDS_TO_SCHEDULE_CAP,
        or DEFAULT_MAX_WORDS_TO_SCHEDULE if the value is invalid.
        """
        from zeeguu.core.word_scheduling.basicSR.basicSR import (
            DEFAULT_MAX_WORDS_TO_SCHEDULE,
            MAX_WORDS_TO_SCHEDULE_CAP,
        )

        try:
            value_as_int = int(value)
            # Cap at maximum to prevent SQL errors with huge LIMIT values
            # Also ensure minimum of 1
            return min(max(value_as_int, 1), MAX_WORDS_TO_SCHEDULE_CAP)
        except (ValueError, TypeError, OverflowError):
            # If value is invalid, return default
            return DEFAULT_MAX_WORDS_TO_SCHEDULE

    @classmethod
    def get_max_words_to_schedule(cls, user):
        from zeeguu.core.word_scheduling.basicSR.basicSR import (
            DEFAULT_MAX_WORDS_TO_SCHEDULE,
        )

        max_words_to_schedule = UserPreference.query.filter_by(
            user_id=user.id, key=cls.MAX_WORDS_TO_SCHEDULE
        ).all()

        if len(max_words_to_schedule) == 0:
            return DEFAULT_MAX_WORDS_TO_SCHEDULE

        return cls.validate_max_words_to_schedule(max_words_to_schedule[0].value)

    @classmethod
    def get_productive_exercises_setting(cls, user: User):
        produtive_setting = UserPreference.query.filter_by(
            user_id=user.id, key=cls.PRODUCTIVE_EXERCISES
        ).first()
        return produtive_setting.value

    @classmethod
    def is_productive_exercises_preference_enabled(cls, user: User):
        return cls.get_productive_exercises_setting(user) == "true"

    @classmethod
    def is_filter_disturbing_content_enabled(cls, user: User):
        """Check if user has enabled filtering of disturbing content. Default: False."""
        filter_setting = UserPreference.query.filter_by(
            user_id=user.id, key=cls.FILTER_DISTURBING_CONTENT
        ).first()
        return filter_setting and filter_setting.value == "true"

    @classmethod
    def get_word_scheduling_strategy(cls, user: User):
        """One of WORD_SCHEDULING_STRATEGIES; when unset, the default for the
        account's age (default_word_scheduling_strategy)."""
        setting = UserPreference.query.filter_by(
            user_id=user.id, key=cls.WORD_SCHEDULING_STRATEGY
        ).first()
        if setting and setting.value in cls.WORD_SCHEDULING_STRATEGIES:
            return setting.value
        return cls.default_word_scheduling_strategy(user)

    @classmethod
    def default_word_scheduling_strategy(cls, user: User):
        created_at = user.created_at
        if created_at and created_at >= cls.FREQUENCY_PRIORITY_DEFAULT_FROM:
            return cls.FREQUENCY_PRIORITY
        return cls.FIRST_COME

    @classmethod
    def is_email_on_article_shared_enabled(cls, user: User):
        """Whether to email the user when a friend shares an article. Default: True
        (opt-out) — a shared article the recipient never hears about is a dead share."""
        setting = UserPreference.query.filter_by(
            user_id=user.id, key=cls.EMAIL_ON_ARTICLE_SHARED
        ).first()
        return setting is None or setting.value == "true"

    @classmethod
    def is_show_easier_articles_enabled(cls, user: User):
        """Whether to ALSO show articles below the user's CEFR level (not just at
        level). Helps advanced/native readers and thin-inventory languages whose
        at-level feed would otherwise be near-empty. Default: False.

        INERT since the feed stopped filtering by CEFR level altogether (see
        build_elastic_recommender_query) — every article is already shown, so
        there is nothing left for this to widen. Kept until the web toggle in
        Settings > Feed Preferences is removed or repurposed."""
        setting = UserPreference.query.filter_by(
            user_id=user.id, key=cls.SHOW_EASIER_ARTICLES
        ).first()
        return setting and setting.value == "true"

    @classmethod
    def parse_daily_goal_minutes(cls, value):
        """A goal as sent by a client, as an int from DAILY_GOAL_CHOICES; None
        when it is not one of them."""
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            return None
        return minutes if minutes in cls.DAILY_GOAL_CHOICES else None

    @classmethod
    def study_reminder_error(cls, key, value):
        """Why a study reminder value sent by a client is refused; None when it
        is fine or not one of the study reminder keys."""
        if key == cls.STUDY_REMINDER_ENABLED and value not in ("true", "false"):
            return f"{key} must be true or false"
        if key == cls.STUDY_REMINDER_TIME and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
            return f"{key} must be a time as HH:MM"
        if key == cls.NOTIFICATIONS_PERMISSION and value not in cls.NOTIFICATIONS_PERMISSIONS:
            return f"{key} must be one of {', '.join(cls.NOTIFICATIONS_PERMISSIONS)}"
        return None

    @classmethod
    def get_daily_goal_minutes(cls, user: User):
        # .first(), not get()'s .one(): user_preference has no unique index on
        # (user_id, key), so two concurrent saves can leave two rows, and this
        # runs on every session update -- a duplicate must not 500 them all.
        row = (
            cls.query.filter_by(user_id=user.id, key=cls.DAILY_GOAL_MINUTES)
            .order_by(cls.id.desc())
            .first()
        )
        stored = cls.parse_daily_goal_minutes(row.value if row else None)
        return stored or cls.DEFAULT_DAILY_GOAL_MINUTES

    @classmethod
    def set_daily_goal_minutes(cls, session, user: User, minutes: int):
        cls.set_dropping_duplicates(session, user, cls.DAILY_GOAL_MINUTES, str(minutes))

    @classmethod
    def set_dropping_duplicates(cls, session, user: User, key: str, value: str):
        """Writes the newest row and drops any duplicates, without committing.
        user_preference has no unique index on (user_id, key), so two
        concurrent first saves can leave two rows; find_or_create's .one()
        would then 500 on every later save, and readers must all see one value."""
        rows = cls.query.filter_by(user_id=user.id, key=key).order_by(cls.id.desc()).all()
        for duplicate in rows[1:]:
            session.delete(duplicate)
        row = rows[0] if rows else cls(user, key)
        row.value = value
        session.add(row)

    @classmethod
    def get_daily_goal_ms(cls, user: User):
        return cls.get_daily_goal_minutes(user) * 60_000

    @classmethod
    def parse_audio_lesson_minutes(cls, value):
        """A lesson length as sent by a client, as an int from
        LESSON_MINUTES_CHOICES; None when it is not one of them."""
        from zeeguu.core.audio_lessons.lesson_tuning import LESSON_MINUTES_CHOICES

        try:
            minutes = int(value)
        except (TypeError, ValueError):
            return None
        return minutes if minutes in LESSON_MINUTES_CHOICES else None

    @classmethod
    def get_audio_lesson_minutes(cls, user: User):
        """The length the learner set; None when they have not set one."""
        row = (
            cls.query.filter_by(user_id=user.id, key=cls.AUDIO_LESSON_MINUTES)
            .order_by(cls.id.desc())
            .first()
        )
        return cls.parse_audio_lesson_minutes(row.value if row else None)

    @classmethod
    def set_audio_lesson_minutes(cls, session, user: User, minutes: int):
        cls.set_dropping_duplicates(session, user, cls.AUDIO_LESSON_MINUTES, str(minutes))

    @classmethod
    def get_audio_lesson_character(cls, user: User):
        """'man' or 'woman' when the learner chose one; None for either or unset."""
        value = cls.get(user, cls.AUDIO_LESSON_CHARACTER)
        return value if value in cls.AUDIO_LESSON_CHARACTERS and value != "either" else None

    @classmethod
    def daily_audio_lesson_type_key(cls, language_code: str):
        return f"{cls.DAILY_AUDIO_LESSON_TYPE_PREFIX}{language_code}"

    @classmethod
    def daily_audio_lesson_suggestion_key(cls, language_code: str):
        return f"{cls.DAILY_AUDIO_LESSON_SUGGESTION_PREFIX}{language_code}"

    @classmethod
    def get_daily_audio_lesson_config(cls, user: User, language_code: str):
        """The user's configured daily audio lesson for a given language.

        :return: (lesson_type, raw_suggestion). lesson_type is None when the user
                 has not set up a daily lesson for this language (daily lesson off).
                 raw_suggestion is the verbatim subject the user typed (None for the
                 three_words_lesson type, which needs no subject).
        """
        lesson_type = cls.get(user, cls.daily_audio_lesson_type_key(language_code))
        suggestion = cls.get(user, cls.daily_audio_lesson_suggestion_key(language_code))
        return lesson_type, suggestion

    # Generic preference handling
    # ---------------------------

    @classmethod
    def _find(cls, user: User, key: str):
        return cls.query.filter_by(user=user, key=key).one()

    @classmethod
    def stored_values(cls, user: User, keys):
        """{key: value} as stored, None for a key with no row; the newest row
        of a key stored twice, as all_for_user reads it. No defaults: a
        change from "not set" is a change."""
        rows = (
            cls.query.filter(cls.user_id == user.id, cls.key.in_(keys))
            .order_by(cls.id)
            .all()
        )
        values = dict.fromkeys(keys)
        for row in rows:
            values[row.key] = row.value
        return values

    @classmethod
    def all_for_user(cls, user: User):
        preferences_dict = {}
        # By id, so a key stored twice reads as its newest row, as the
        # single-key getters (get_daily_goal_minutes) read it.
        all_preference_objects = cls.query.filter_by(user=user).order_by(cls.id).all()

        for each in all_preference_objects:
            preferences_dict[each.key] = each.value

        # This suboptimal - it would be faster to create a migration script and make sure that all
        # users have this preference set; also, it should be initialized with the default value
        if cls.MAX_WORDS_TO_SCHEDULE not in preferences_dict.keys():
            from zeeguu.core.word_scheduling.basicSR.basicSR import (
                DEFAULT_MAX_WORDS_TO_SCHEDULE,
            )

            preferences_dict[cls.MAX_WORDS_TO_SCHEDULE] = DEFAULT_MAX_WORDS_TO_SCHEDULE

        # Always present, so clients show the strategy the scheduler uses,
        # which for an unset one depends on the account's age.
        if preferences_dict.get(cls.WORD_SCHEDULING_STRATEGY) not in cls.WORD_SCHEDULING_STRATEGIES:
            preferences_dict[cls.WORD_SCHEDULING_STRATEGY] = cls.default_word_scheduling_strategy(user)

        # Always present, so clients show the goal the streak is counted with.
        stored_goal = cls.parse_daily_goal_minutes(preferences_dict.get(cls.DAILY_GOAL_MINUTES))
        preferences_dict[cls.DAILY_GOAL_SET] = (
            "true" if stored_goal in cls.DAILY_GOAL_PICKER_CHOICES else "false"
        )
        preferences_dict[cls.DAILY_GOAL_MINUTES] = str(stored_goal or cls.DEFAULT_DAILY_GOAL_MINUTES)

        # Always present too: the slider shows the length the next lesson is
        # written for, also when the learner never set one.
        if user.learned_language is not None:
            from zeeguu.core.audio_lessons.lesson_tuning import lesson_minutes_for

            preferences_dict[cls.AUDIO_LESSON_MINUTES] = str(
                lesson_minutes_for(user, user.learned_language)
            )

        return preferences_dict

    @classmethod
    def find(cls, user: User, key: str):
        """
        :return: A UserPreference object, or None if none was found
        """
        try:
            return cls._find(user, key)
        except NoResultFound:
            return None

    @classmethod
    def get(cls, user: User, key: str):
        """
        :return: the value of a preference or None if none was found
        """
        try:
            return cls._find(user, key).value
        except NoResultFound:
            return None

    @classmethod
    def set(cls, session, user: User, key: str, value: str):
        """

            Generic method for setting a preference value.

        :param session:
        :param user:
        :param key:
        :param value:
        :return:
        """
        pref = cls.find_or_create(session, user, key)
        pref.value = value
        session.add(pref)
        session.commit()

    @classmethod
    def find_or_create(cls, session, user: User, key: str, value: str = None):
        try:
            return cls._find(user, key)
        except NoResultFound:
            try:
                new_pref = cls(user, key, value)
                session.add(new_pref)
                session.commit()
                log("Created new preference since original was missing")
                return new_pref
            except sqlalchemy.exc.IntegrityError:
                for _ in range(10):
                    try:
                        session.rollback()
                        pref = cls._find(user, key)
                        log("Successfully avoided race condition. Nice! ")
                        return pref
                    except sqlalchemy.orm.exc.NoResultFound:
                        time.sleep(0.3)
                        continue
                    break
