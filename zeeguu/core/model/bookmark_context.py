from zeeguu.core.model.language import Language
from zeeguu.core.model.new_text import NewText

from .db import db
import sqlalchemy
import time
import json


class ContextIdentifier:
    def __init__(
        self,
        context_type: str,
        article_fragment_id=None,
        article_id=None,
        video_id=None,
        video_caption_id=None,
    ):
        self.context_type = context_type
        self.article_fragment_id = article_fragment_id
        self.article_id = article_id
        self.video_id = video_id
        self.video_caption_id = video_caption_id

    def __repr__(self):
        return f"<ContextIdentifier context_type={self.context_type}>"

    @classmethod
    def from_dictionary(cls, dictionary):
        assert dictionary is not None
        assert "context_type" in dictionary, f"Context type must be provided"

        return ContextIdentifier(
            dictionary.get("context_type", None),
            dictionary.get("article_fragment_id", None),
            dictionary.get("article_id", None),
            video_id=dictionary.get("video_id", None),
            video_caption_id=dictionary.get("video_caption_id", None),
        )

    @classmethod
    def from_json_string(cls, json_string):
        return cls.from_dictionary(json.loads(json_string))

    def as_dictionary(self):
        return {
            "context_type": self.context_type,
            "article_fragment_id": self.article_fragment_id,
            "article_id": self.article_id,
            "video_id": self.video_id,
            "video_caption_id": self.video_caption_id,
        }


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
