from datetime import datetime

import sqlalchemy
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import relationship

from zeeguu.core.model.article import Article
from zeeguu.core.model.bookmark_context import BookmarkContext
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.db import db
from zeeguu.core.model.meaning import Meaning
from zeeguu.core.model.source import Source
from zeeguu.core.model.text import Text
from zeeguu.core.model.user_word import UserWord


class Bookmark(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

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

    starred = db.Column(db.Boolean, default=False)
    
    # Track where this translation/bookmark was created
    translation_source = db.Column(db.Enum('reading', 'exercise', 'article_preview'), default='reading')

    user_word_id = db.Column(db.Integer, db.ForeignKey("user_word.id"), nullable=False)
    user_word = db.relationship(UserWord, foreign_keys=[user_word_id])

    def __init__(
        self,
        user_word: "UserWord",
        source: Source,
        text: str,
        time: datetime,
        sentence_i: int = None,
        token_i: int = None,
        total_tokens: int = None,
        context: BookmarkContext = None,
        translation_source: str = 'reading',
    ):
        self.user_word = user_word
        self.source = source
        self.text = text
        self.time = time
        self.translation_source = translation_source
        self.sentence_i = sentence_i
        self.token_i = token_i
        self.total_tokens = total_tokens
        self.context = context

    def __repr__(self):
        return f"Bookmark ({self.id}): {self.user_word.meaning} {self.context.get_content()[0:10]}"

    def get_context(self):
        if self.context:
            return self.context.get_content()
        else:
            return self.text.content

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

            title_context = ArticleTitleContext.find_by_bookmark(self)
            if title_context:
                return Article.find_by_id(title_context.article_id).title
            else:
                # Fallback: context mapping is missing
                return "[Title not available]"
        if self.context.context_type.type == ContextType.ARTICLE_FRAGMENT:
            from zeeguu.core.model.article_fragment_context import (
                ArticleFragmentContext,
            )

            fragment_context = ArticleFragmentContext.find_by_bookmark(self)
            if fragment_context and fragment_context.article_fragment:
                return Article.find_by_id(
                    fragment_context.article_fragment.article_id
                ).title
            else:
                # Fallback: context mapping is missing
                return "[Title not available]"
        if self.context.context_type.type == ContextType.ARTICLE_SUMMARY:
            from zeeguu.core.model.article_summary_context import (
                ArticleSummaryContext,
            )

            summary_context = ArticleSummaryContext.find_by_bookmark(self)
            if summary_context:
                return Article.find_by_id(summary_context.article_id).title
            else:
                # Fallback: context mapping is missing
                return "[Title not available]"
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
            origin=self.user_word.meaning.origin.content,
            translation=self.user_word.meaning.translation.content,
            source_id=self.source_id,
            t_sentence_i=self.sentence_i,
            t_token_i=self.token_i,
            t_total_token=self.total_tokens,
            user_word_id=self.user_word_id,
            translation_source=self.translation_source,
        )

        result["from"] = self.user_word.meaning.origin.content
        result["to"] = self.user_word.meaning.translation.content
        result["fit_for_study"] = self.user_word.fit_for_study
        result["url"] = self.text.url()
        
        # Add word rank if available
        word_rank = self.user_word.meaning.origin.rank
        result["origin_rank"] = word_rank if word_rank != 100000 else ""

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

            tokenizer = get_tokenizer(
                self.user_word.meaning.origin.language, TOKENIZER_MODEL
            )
            result["context_tokenized"] = tokenizer.tokenize_text(
                self.context.get_content(),
                flatten=False,
                start_token_i=self.context.token_i,
                start_sentence_i=self.context.sentence_i,
            )

        return result

    def add_new_exercise(self, exercise):
        # delegates to the usr_meaning for backwards compat with tests
        self.user_word.add_new_exercise(exercise)

    def add_new_exercise_result(
        self,
        exercise_source,
        exercise_outcome,
        exercise_solving_speed,
        session_id: int,
        other_feedback="",
        time: datetime = None,
    ):
        self.user_word.add_new_exercise_result(
            exercise_source,
            exercise_outcome,
            exercise_solving_speed,
            session_id,
            other_feedback,
            time,
        )

    def get_context_identifier(self):
        from zeeguu.core.model.context_identifier import ContextIdentifier
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
                case ContextType.ARTICLE_SUMMARY:
                    context_identifier.article_id = (
                        result.article_id if result else None
                    )
                case ContextType.VIDEO_TITLE:
                    context_identifier.video_id = result.video_id if result else None
                case ContextType.VIDEO_CAPTION:
                    context_identifier.video_caption_id = (
                        result.caption_id if result else None
                    )
                case ContextType.EXAMPLE_SENTENCE:
                    context_identifier.example_sentence_id = (
                        result.example_sentence_id if result else None
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
        return context_identifier.create_context_mapping(session, self, commit=commit)

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
        translation_source: str = 'reading',
    ):
        """
        if the bookmark does not exist, it creates it and returns it
        if it exists, it ** updates the translation** and returns the bookmark object
        """

        meaning = Meaning.find_or_create(
            session, _origin, _origin_lang, _translation, _translation_lang
        )

        user_word = UserWord.find_or_create(session, user, meaning)

        source = Source.find_by_id(source_id)

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
            bookmark = Bookmark.find_by_usermeaning_and_context(user_word, context)

        except sqlalchemy.orm.exc.NoResultFound as e:
            bookmark = cls(
                user_word,
                source,
                text,
                now,
                sentence_i=sentence_i,
                token_i=token_i,
                total_tokens=total_tokens,
                context=context,
                translation_source=translation_source,
            )
        except Exception as e:
            raise e

        session.add(bookmark)
        bookmark.create_context_mapping(session, context_identifier, commit=False)
        session.add(bookmark)
        session.commit()

        # Set this bookmark as the preferred bookmark if none is set
        if user_word.preferred_bookmark is None:
            user_word.preferred_bookmark = bookmark
            session.add(user_word)

        # Update fit_for_study after bookmark is created
        user_word.update_fit_for_study(session)
        session.commit()

        return bookmark

    def sorted_exercise_log(self):
        from zeeguu.core.model.sorted_exercise_log import SortedExerciseLog

        return SortedExerciseLog(self)

    def update_fit_for_study(self):
        self.user_word.update_fit_for_study()

    @classmethod
    def find_by_specific_user(cls, user):
        return (
            cls.query.join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(UserWord.user_id == user.id)
            .all()
        )

    @classmethod
    def find_all(cls):
        return cls.query.filter().all()

    @classmethod
    def find_all_for_context_and_user(cls, context, user):
        return (
            Bookmark.query.join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(UserWord.user_id == user.id)
            .filter(Bookmark.context_id == context.id)
            .all()
        )

    @classmethod
    def find_all_for_user_and_article(cls, user, article):
        return (
            cls.query.join(Source)
            .join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(UserWord.user_id == user.id)
            .filter(Source.id == article.source_id)
            .all()
        )

    @classmethod
    def find_all_for_text_and_user(cls, text, user):
        # TODO: Tiago remember to also delete the only places that calls this
        return (
            cls.query.join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(UserWord.user_id == user.id)
            .filter(Bookmark.text == text)
            .all()
        )

    @classmethod
    def find_all_for_user_and_source(cls, user, source):
        return (
            cls.query.filter(cls.source_id == source.id)
            .join(UserWord, Bookmark.user_word_id == UserWord.id)
            .filter(UserWord.user_id == user.id)
            .all()
        )

    @classmethod
    def find(cls, b_id):
        return cls.query.filter_by(id=b_id).one()

    @classmethod
    def find_by_usermeaning_and_context(cls, user_word, context):
        return cls.query.filter_by(user_word=user_word, context=context).one()

    @classmethod
    def exists(cls, source, text, context, user_word):
        try:
            cls.query.filter_by(
                source=source, text=text, context=context, user_word=user_word
            ).one()
            return True
        except NoResultFound:
            return False
