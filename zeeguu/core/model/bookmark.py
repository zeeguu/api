from datetime import datetime

import sqlalchemy
from sqlalchemy import Column, ForeignKey, Integer, Table
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from zeeguu.core.model.caption import Caption
from zeeguu.core.model.video import Video
from zeeguu.core.model.meaning import Meaning
from zeeguu.logging import log
from zeeguu.core.bookmark_quality.fit_for_study import fit_for_study

from zeeguu.core.model.article import Article
from zeeguu.core.model.exercise import Exercise
from zeeguu.core.model.exercise_outcome import ExerciseOutcome
from zeeguu.core.model.exercise_source import ExerciseSource
from zeeguu.core.model.source import Source
from zeeguu.core.model.text import Text
from zeeguu.core.model.user import User
from zeeguu.core.model.learning_cycle import LearningCycle
from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
from zeeguu.core.model.bookmark_context import BookmarkContext, ContextIdentifier

from zeeguu.core.model import db

from zeeguu.core.util.encoding import datetime_to_json

from wordstats import Word


bookmark_exercise_mapping = Table(
    "bookmark_exercise_mapping",
    db.Model.metadata,
    Column("bookmark_id", Integer, ForeignKey("bookmark.id")),
    Column("exercise_id", Integer, ForeignKey("exercise.id")),
)


class Bookmark(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    meaning_id = db.Column(db.Integer, db.ForeignKey(Meaning.id), nullable=False)
    meaning = db.relationship(Meaning, backref="bookmarks")

    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    user = db.relationship(User)

    source_id = db.Column(db.Integer, db.ForeignKey(Source.id))
    source = db.relationship(Source)

    text_id = db.Column(db.Integer, db.ForeignKey(Text.id))
    text = db.relationship(Text)

    context_id = db.Column(db.Integer, db.ForeignKey(BookmarkContext.id))
    context = db.relationship(BookmarkContext)

    """
    The bookmarks will have a reference to the sentence / token in relation
    to the context they are associaed with. So sentence_i and token_i refer to the
    start of the context. 

    Since the words can be merged to give a better translation, in those cases we 
    have the first word and then the total tokens after it that were merged.
    """
    sentence_i = db.Column(db.Integer)
    token_i = db.Column(db.Integer)
    total_tokens = db.Column(db.Integer)

    time = db.Column(db.DateTime)

    exercise_log = relationship(
        Exercise, secondary="bookmark_exercise_mapping", order_by="Exercise.id"
    )

    starred = db.Column(db.Boolean, default=False)

    fit_for_study = db.Column(db.Boolean)

    learned_time = db.Column(db.DateTime)

    learning_cycle = db.Column(db.Integer)

    level = db.Column(db.Integer)

    user_preference = db.Column(db.Integer)

    bookmark = db.relationship("WordToStudy", backref="bookmark", passive_deletes=True)

    def __init__(
        self,
        meaning: "Meaning",
        user: "User",
        source: Source,
        text: str,
        time: datetime,
        learning_cycle: int = LearningCycle.NOT_SET,
        sentence_i: int = None,
        token_i: int = None,
        total_tokens: int = None,
        context: BookmarkContext = None,
        level: int = 0,
    ):
        self.meaning = meaning
        self.user = user
        self.source = source
        self.time = time
        self.text = text
        self.starred = False
        self.learning_cycle = learning_cycle
        self.user_preference = UserWordExPreference.NO_PREFERENCE
        self.sentence_i = sentence_i
        self.token_i = token_i
        self.total_tokens = total_tokens
        self.context = context
        self.level = level
        self.fit_for_study = fit_for_study(self)

    def __repr__(self):
        return "Bookmark[{3} of {4}: {0}->{1} in '{2}...']\n".format(
            self.meaning.origin.word,
            self.meaning.translation.word,
            self.context.get_content()[0:10],
            self.id,
            self.user_id,
        )

    def is_learned(self):
        return self.learned_time is not None

    def get_context(self):
        if self.context:
            return self.context.get_content()
        else:
            return self.text.content

    def get_scheduler(self):
        from zeeguu.core.word_scheduling import get_scheduler

        return get_scheduler(self.user)

    def add_new_exercise(self, exercise):
        self.exercise_log.append(exercise)

    def translations_rendered_as_text(self):
        return self.meaning.translation.word

    def should_be_studied(self):
        return (self.starred or self.fit_for_study) and not self.is_learned()

    def content_is_not_too_long(self):
        return len(self.get_context()) < 60

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

    def add_new_exercise_result(
        self,
        exercise_source: ExerciseSource,
        exercise_outcome: ExerciseOutcome,
        exercise_solving_speed,
        session_id: int,
        other_feedback="",
        time: datetime = None,
    ):
        if not time:
            time = datetime.now()
        exercise = Exercise(
            exercise_outcome,
            exercise_source,
            exercise_solving_speed,
            time,
            session_id,
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
        source = ExerciseSource.find_or_create(db_session, exercise_source)
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

    def to_json(
        self,
        with_context,
        with_exercise_info=False,
        with_title=False,
        with_context_tokenized=False,
    ):
        return self.as_dictionary(
            with_exercise_info=with_exercise_info,
            with_title=with_title,
            with_context=with_context,
            with_context_tokenized=with_context_tokenized,
        )

    def get_source_title(self):
        from zeeguu.core.model.context_type import ContextType
        from zeeguu.core.model.article import Article
        from zeeguu.core.model.video import Video

        if self.context.context_type.type == ContextType.ARTICLE_TITLE:
            from zeeguu.core.model.article_title_context import ArticleTitleContext

            return Article.find_by_id(
                ArticleTitleContext.find_by_bookmark(self).article_id
            ).title
        if self.context.context_type.type == ContextType.ARTICLE_FRAGMENT:
            from zeeguu.core.model.article_fragment_context import (
                ArticleFragmentContext,
            )

            return Article.find_by_id(
                ArticleFragmentContext.find_by_bookmark(
                    self
                ).article_fragment.article_id
            ).title
        if self.context.context_type.type == ContextType.VIDEO_TITLE:
            from zeeguu.core.model.video_title_context import VideoTitleContext

            return Video.find_by_id(
                VideoTitleContext.find_by_bookmark(self).video_id
            ).title

        if self.context.context_type.type == ContextType.VIDEO_CAPTION:
            from zeeguu.core.model.video_caption_context import VideoCaptionContext

            return Video.find_by_id(
                VideoCaptionContext.find_by_bookmark(self).caption.video_id
            ).title

        return None

    def as_dictionary(
        self,
        with_exercise_info=False,
        with_title=False,
        with_context=True,
        with_context_tokenized=False,
    ):
        result = dict(
            id=self.id,
            origin=self.meaning.origin.word,
            translation=self.meaning.translation.word,
            source_id=self.source_id,
            t_sentence_i=self.sentence_i,
            t_token_i=self.token_i,
            t_total_token=self.total_tokens,
        )

        if with_context:
            context_info_dict = dict(
                context=self.get_context(),
                context_sent=self.context.sentence_i,
                context_token=self.context.token_i,
            )
            if self.context.context_type:
                result["context_identifier"] = self.get_context_identifier()
            result = {**result, **context_info_dict}

        bookmark_title = ""

        if with_title:
            try:
                bookmark_title = self.get_source_title()
            except Exception as e:
                from zeeguu.logging import print_and_log_to_sentry

                print(f"could not find article title for bookmark with id: {self.id}")
                print_and_log_to_sentry(e)

            result["title"] = bookmark_title

        if with_context_tokenized:
            from zeeguu.core.tokenization import TOKENIZER_MODEL, get_tokenizer

            tokenizer = get_tokenizer(self.meaning.origin.language, TOKENIZER_MODEL)
            result["context_tokenized"] = tokenizer.tokenize_text(
                self.context.get_content(),
                flatten=False,
                start_token_i=self.context.token_i,
                start_sentence_i=self.context.sentence_i,
            )

        if not with_exercise_info:
            return result

        try:
            translation_word = self.meaning.translation.word
            translation_language = self.meaning.translation.language.code
        except AttributeError as e:
            translation_word = ""
            translation_language = ""
            log(
                f"Exception caught: for some reason there was no translation for {self.id}"
            )
            print(str(e))

        word_info = Word.stats(
            self.meaning.origin.word, self.meaning.origin.language.code
        )

        learned_datetime = (
            str(self.learned_time.date()) if self.learned_time is not None else ""
        )

        created_day = "today" if self.time.date() == datetime.now().date() else ""

        # Fetch the BasicSRSchedule instance associated with the current bookmark
        from zeeguu.core.word_scheduling import ONE_DAY
        from zeeguu.core.word_scheduling.basicSR.basicSR import _get_end_of_today

        try:
            scheduler = self.get_scheduler()
            bookmark_scheduler = scheduler.query.filter(
                scheduler.bookmark_id == self.id
            ).one()
            cooling_interval_in_days = bookmark_scheduler.cooling_interval // ONE_DAY
            next_practice_time = bookmark_scheduler.next_practice_time
            can_update_schedule = next_practice_time <= _get_end_of_today()
            consecutive_correct_answers = bookmark_scheduler.consecutive_correct_answers
            is_last_in_cycle = (
                bookmark_scheduler.get_max_interval()
                == bookmark_scheduler.cooling_interval
            )

            is_about_to_be_learned = bookmark_scheduler.is_about_to_be_learned()

        except sqlalchemy.exc.NoResultFound:
            cooling_interval_in_days = None
            can_update_schedule = None
            consecutive_correct_answers = None
            is_last_in_cycle = None
            is_about_to_be_learned = None

        exercise_info_dict = dict(
            to=translation_word,
            from_lang=self.meaning.origin.language.code,
            to_lang=translation_language,
            url=self.text.url(),
            origin_importance=word_info.importance,
            learned_datetime=learned_datetime,
            origin_rank=word_info.rank if word_info.rank != 100000 else "",
            starred=self.starred if self.starred is not None else False,
            article_id=self.text.article_id if self.text.article_id else "",
            source_id=self.source_id,
            created_day=created_day,  # human readable stuff...
            time=datetime_to_json(self.time),
            fit_for_study=self.fit_for_study == 1,
            level=self.level,
            cooling_interval=cooling_interval_in_days,
            learning_cycle=self.learning_cycle,
            is_last_in_cycle=is_last_in_cycle,
            is_about_to_be_learned=is_about_to_be_learned,
            can_update_schedule=can_update_schedule,
            user_preference=self.user_preference,
            consecutive_correct_answers=consecutive_correct_answers,
            context_in_content=self.text.in_content,
            left_ellipsis=self.context.left_ellipsis,
            right_ellipsis=self.context.right_ellipsis,
        )

        exercise_info_dict["from"] = self.meaning.origin.word
        result = {**result, **exercise_info_dict}
        return result

    def get_context_identifier(self):
        from zeeguu.core.model.bookmark_context import ContextIdentifier
        from zeeguu.core.model.context_type import ContextType

        context_type = self.context.context_type.type
        context_identifier = ContextIdentifier(
            context_type,
        )
        context_type_table = ContextType.get_table_corresponding_to_type(context_type)
        if context_type_table:
            result = context_type_table.find_by_bookmark(self)
            match context_type:
                case ContextType.ARTICLE_FRAGMENT:
                    context_identifier.article_fragment_id = (
                        result.article_fragment_id if result else None
                    )
                case ContextType.ARTICLE_TITLE:
                    context_identifier.article_id = (
                        result.article_id if result else None
                    )
                case ContextType.VIDEO_TITLE:
                    context_identifier.video_id = result.video_id if result else None
                case ContextType.VIDEO_CAPTION:
                    context_identifier.video_caption_id = (
                        result.caption_id if result else None
                    )
                case _:
                    print("### Got a type without a mapped table!")
        return context_identifier.as_dictionary()

    def create_context_mapping(
        self,
        session,
        context_identifier: ContextIdentifier,
        commit=False,
    ):
        """
        Creates a mapping between a context and a context source.

        :param context: The Context object to map.
        :param context_id: The ID of the context source.

        :return: The created mapping object.
        """
        from zeeguu.core.model.context_type import ContextType

        if not self.context or self.context.context_type == None:
            return None
        mapped_context = None
        print("Context type is: ", self.context.context_type.type)
        context_specific_table = ContextType.get_table_corresponding_to_type(
            self.context.context_type.type
        )
        match self.context.context_type.type:
            case ContextType.ARTICLE_FRAGMENT:
                if context_identifier.article_fragment_id is None:
                    return None
                from zeeguu.core.model.article_fragment import ArticleFragment

                fragment = ArticleFragment.find_by_id(
                    context_identifier.article_fragment_id
                )
                mapped_context = context_specific_table.find_or_create(
                    session,
                    self,
                    fragment,
                    commit=commit,
                )
                session.add(mapped_context)
            case ContextType.ARTICLE_TITLE:
                if context_identifier.article_id is None:
                    return None
                article = Article.find_by_id(context_identifier.article_id)
                mapped_context = context_specific_table.find_or_create(
                    session, self, article, commit=commit
                )
                session.add(mapped_context)
            case ContextType.VIDEO_TITLE:
                if context_identifier.video_id is None:
                    return None
                video = Video.find_by_id(context_identifier.video_id)
                mapped_context = context_specific_table.find_or_create(
                    session, self, video, commit=commit
                )
                session.add(mapped_context)
            case ContextType.VIDEO_CAPTION:
                if context_identifier.video_caption_id is None:
                    return None
                video_caption = Caption.find_by_id(context_identifier.video_caption_id)
                mapped_context = context_specific_table.find_or_create(
                    session, self, video_caption, commit=commit
                )
                session.add(mapped_context)
            case _:
                print(
                    f"## Something went wrong, the context {self.context.context_type.type} did not match any case."
                )

        return mapped_context

    @classmethod
    def find_or_create(
        cls,
        session,
        user,
        _origin: str,
        _origin_lang: str,
        _translation: str,
        _translation_lang: str,
        _context: str,
        article_id: int,
        source_id: int,
        learning_cycle: int = LearningCycle.NOT_SET,
        sentence_i: int = None,
        token_i: int = None,
        total_tokens: int = None,
        c_paragraph_i: int = None,
        c_sentence_i: int = None,
        c_token_i: int = None,
        in_content: bool = None,
        left_ellipsis: bool = None,
        right_ellipsis: bool = None,
        context_identifier: ContextIdentifier = None,
        level: int = 0,
    ):
        """
        if the bookmark does not exist, it creates it and returns it
        if it exists, it ** updates the translation** and returns the bookmark object
        """

        meaning = Meaning.find_or_create(
            session, _origin, _origin_lang, _translation, _translation_lang
        )

        source = Source.find_by_id(source_id)
        print("Source retrieved: ", source)
        # TODO: This will be temporary.
        article = None
        if source_id and not article_id:
            article = Article.find_by_source_id(source_id)
        if article_id:
            article = Article.query.filter_by(id=article_id).one()

        context = BookmarkContext.find_or_create(
            session,
            _context,
            context_identifier.context_type if context_identifier else None,
            meaning.origin.language,
            c_sentence_i,
            c_token_i,
            left_ellipsis,
            right_ellipsis,
        )

        text = Text.find_or_create(
            session,
            _context,
            meaning.origin.language,
            None,
            article,
            c_paragraph_i,
            c_sentence_i,
            c_token_i,
            in_content,
            left_ellipsis,
            right_ellipsis,
        )

        now = datetime.now()

        try:
            # try to find this bookmark
            bookmark = Bookmark.find_by_meaning_and_context(user, meaning, context)

        except sqlalchemy.orm.exc.NoResultFound as e:
            bookmark = cls(
                meaning,
                user,
                source,
                text,
                now,
                learning_cycle=learning_cycle,
                sentence_i=sentence_i,
                token_i=token_i,
                total_tokens=total_tokens,
                context=context,
                level=level,
            )
        except Exception as e:
            raise e

        session.add(bookmark)
        bookmark.create_context_mapping(session, context_identifier, commit=False)
        session.add(bookmark)
        session.commit()
        return bookmark

    def sorted_exercise_log(self):
        from zeeguu.core.model.sorted_exercise_log import SortedExerciseLog

        return SortedExerciseLog(self)

    @classmethod
    def find_by_specific_user(cls, user):
        return cls.query.filter_by(user=user).all()

    @classmethod
    def find_all(cls):
        return cls.query.filter().all()

    @classmethod
    def find_all_for_context_and_user(cls, context, user):
        return Bookmark.query.filter_by(context=context, user=user).all()

    @classmethod
    def find_all_for_user_and_article(cls, user, article):
        return (
            cls.query.join(Source)
            .filter(Source.id == article.source_id)
            .filter(Bookmark.user == user)
            .all()
        )

    @classmethod
    def find_all_for_text_and_user(cls, text, user):
        # TODO: Tiago remember to also delete the only places that calls this
        return Bookmark.query.filter_by(text=text, user=user).all()

    @classmethod
    def find_all_for_user_and_source(cls, user, source):
        return (
            cls.query.filter(cls.source_id == source.id).filter(cls.user == user).all()
        )

    @classmethod
    def find(cls, b_id):
        return cls.query.filter_by(id=b_id).one()

    @classmethod
    def find_by_meaning_and_context(cls, user, meaning, context):
        return cls.query.filter_by(user=user, meaning=meaning, context=context).one()

    @classmethod
    def exists(cls, bookmark):
        try:
            cls.query.filter_by(meaning_id=bookmark.meaning.id, id=bookmark.id).one()
            return True
        except NoResultFound:
            return False

    def is_learned_based_on_exercise_outcomes(self):
        from zeeguu.core.model.sorted_exercise_log import SortedExerciseLog
        from zeeguu.core.definition_of_learned import (
            is_learned_based_on_exercise_outcomes,
        )

        exercise_log = SortedExerciseLog(self)
        return is_learned_based_on_exercise_outcomes(
            exercise_log, self.learning_cycle == LearningCycle.PRODUCTIVE
        )

    def update_learned_status(self, session):
        from zeeguu.core.definition_of_learned import (
            is_learned_based_on_exercise_outcomes,
        )
        from zeeguu.core.model.sorted_exercise_log import SortedExerciseLog

        """
            To call when something happened to the bookmark,
             that requires it's "learned" status to be updated.
        :param session:
        :return:
        """
        exercise_log = SortedExerciseLog(self)
        is_learned = is_learned_based_on_exercise_outcomes(
            exercise_log, self.learning_cycle == LearningCycle.PRODUCTIVE
        )
        if is_learned:
            log(f"Log: {exercise_log.summary()}: bookmark {self.id} learned!")
            self.learned_time = exercise_log.last_exercise_time()
            session.add(self)
        else:
            log(f"Log: {exercise_log.summary()}: bookmark {self.id} not learned yet.")
