from zeeguu.core.model.language import Language
from zeeguu.core.model.new_text import NewText

from zeeguu.core.model.db import db
import sqlalchemy
import time


class BookmarkContext(db.Model):
    """
    Used to be known as text before. The idea is that now table only stores
    the fragments and then is linked to the diverse sources through mapping tables
    that contain the relevant coordinates.
    """

    from zeeguu.core.model.context_type import ContextType

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    text_id = db.Column(db.Integer, db.ForeignKey(NewText.id))
    text = db.relationship(NewText, foreign_keys="BookmarkContext.text_id")

    context_type_id = db.Column(db.Integer, db.ForeignKey(ContextType.id))
    context_type = db.relationship(
        ContextType, foreign_keys="BookmarkContext.context_type_id"
    )

    language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    language = db.relationship(Language)

    right_ellipsis = db.Column(db.Boolean)
    left_ellipsis = db.Column(db.Boolean)
    sentence_i = db.Column(db.Integer)
    token_i = db.Column(db.Integer)
    cached_tokenized = db.Column(db.JSON, default=None)

    def __init__(
        self,
        text,
        context_type,
        language,
        sentence_i,
        token_i,
        left_ellipsis=None,
        right_ellipsis=None,
    ):
        self.text = text
        self.language = language
        self.context_type = context_type
        self.sentence_i = sentence_i
        self.token_i = token_i
        self.left_ellipsis = left_ellipsis
        self.right_ellipsis = right_ellipsis

    def __repr__(self):
        return f"<BookmarkContext {self.get_content()}>"

    def get_content(self):
        if not self.text:
            return "[Context deleted]"
        return self.text.content

    def get_tokenized(self, session=None):
        """
        Get tokenized content, using cache if available.
        Tokenizes and caches on first access.
        """
        if self.cached_tokenized is not None:
            return self.cached_tokenized

        # Tokenize and cache
        from zeeguu.core.mwe import tokenize_for_reading

        try:
            tokenized = tokenize_for_reading(
                self.get_content(),
                self.language,
                mode="stanza",
                start_token_i=self.token_i,
                start_sentence_i=self.sentence_i,
            )
            self.cached_tokenized = tokenized
            if session:
                session.add(self)
                session.commit()
            return tokenized
        except Exception as e:
            # Return None if tokenization fails
            return None

    def clear_tokenization_cache(self, session=None):
        """
        Clear the cached tokenization.
        Call this when the context content changes.
        """
        self.cached_tokenized = None
        if session:
            session.add(self)
            session.commit()

    def all_bookmarks(self, user):
        from zeeguu.core.model.bookmark import Bookmark

        return Bookmark.find_all_for_context_and_user(self, user)

    def all_bookmarks_for_context(self):
        from zeeguu.core.model.bookmark import Bookmark

        return Bookmark.query.join(self).filter(Bookmark.context_id == self.id).all()

    @classmethod
    def find_all(cls, text, language):
        """
        there could be multiple texts
        in multiple articles actually...
        """
        from zeeguu.core.util import long_hash
        from zeeguu.core.model.new_text import NewText

        hash_string = long_hash(text)
        return (
            cls.query.join(NewText)
            .filter(NewText.content_hash == hash_string)
            .filter(cls.language_id == language.id)
            .all()
        )

    @classmethod
    def find_by_id(cls, context_id):
        try:
            return cls.query.filter_by(id=context_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(
        cls,
        session,
        content,
        context_type: str,
        language,
        sentence_i,
        token_i,
        left_ellipsis=None,
        right_ellipsis=None,
        commit=True,
    ):
        """
        Finds a Context with the given content and language, or creates it if it does
        not exist.

        :param session: The SQLAlchemy session to use.
        :param content: The text content of the context.
        :param language: The Language object representing the language of the context.
        :param left_ellipsis: Whether the context should have a left ellipsis.
        :param right_ellipsis: Whether the context should have a right ellipsis.

        :return: A Context object representing the found or created context.
        """
        from zeeguu.core.model.context_type import ContextType

        text_row = NewText.find_or_create(session, content, commit=commit)
        if context_type:
            context_type = ContextType.find_by_type(context_type)

        try:
            return (
                cls.query.filter(cls.text == text_row)
                .filter(cls.context_type == context_type)
                .filter(cls.language == language)
                .one()
            )
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            try:
                new = cls(
                    text_row,
                    context_type,
                    language,
                    sentence_i,
                    token_i,
                    left_ellipsis,
                    right_ellipsis,
                )
                session.add(new)
                if commit:
                    session.commit()
                return new
            except Exception as e:
                print("Exception was: ", e)
                for i in range(10):
                    try:
                        session.rollback()
                        t = cls.query.filter(cls.text == text_row).one()
                        print("found text after recovering from race")
                        return t
                    except:
                        print(
                            "exception of second degree in BookmarkContext..." + str(i)
                        )
                        time.sleep(0.3)
                        continue
