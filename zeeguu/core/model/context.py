import zeeguu.core
from zeeguu.core.util import text_hash
from zeeguu.core.model import Language
from zeeguu.core.model import db
import sqlalchemy
import re
import time
from enum import Enum


class ContextSources(str, Enum):
    ArticleFragment = "ArticleFragment"
    ArticleTitle = "ArticleTitle"
    ArticleSummary = "ArticleSummary"
    VideoTitle = "VideoTitle"
    VideoSubtitle = "VideoSubtitle"
    WebFragment = "WebFragment"


class Context(db.Model):
    """
    Used to be known as text before. The idea is that now table only stores
    the fragments and then is linked to the diverse sources through mapping tables
    that contain the relevant coordinates.
    """

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(1024))

    content_hash = db.Column(db.String(64))

    language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    language = db.relationship(Language)

    right_ellipsis = db.Column(db.Boolean)
    left_ellipsis = db.Column(db.Boolean)

    def __init__(
        self,
        content,
        language,
        left_ellipsis=None,
        right_ellipsis=None,
    ):
        self.content = content
        self.language = language
        self.content_hash = text_hash(content)
        self.left_ellipsis = left_ellipsis
        self.right_ellipsis = right_ellipsis

    def __repr__(self):
        return f"<Context {self.content}>"

    def update_content(self, new_content):
        self.content = new_content
        self.content_hash = text_hash(new_content)

    def words(self):
        from zeeguu.core.model import UserWord

        for word in re.split(re.compile("[^\\w]+", re.U), self.content):
            yield UserWord.find(word, self.language)

    def all_bookmarks(self, user):
        from zeeguu.core.model import Bookmark

        return Bookmark.find_all_for_text_and_user(self, user)

    def all_bookmarks_for_context(self):
        from zeeguu.core.model import Bookmark

        return Bookmark.query.join(self).filter(Bookmark.context_id == self.id).all()

    @classmethod
    def find_all(cls, text, language):
        """
        there could be multiple texts
        in multiple articles actually...
        """
        hash = text_hash(text)
        return (
            cls.query.filter_by(content_hash=hash)
            .filter_by(language_id=language.id)
            .all()
        )

    @classmethod
    def find_by_id(cls, context_id):
        return cls.query.filter_by(id=context_id).one()

    @classmethod
    def get_context_type_mappings(cls):
        from zeeguu.core.model.article_fragment_context import ArticleFragmentContext
        from zeeguu.core.model.article_title_context import ArticleTitleContext

        CONTEXT_SOURCE_TABLE_MAPPING = {
            ContextSources.ArticleFragment: ArticleFragmentContext,
            ContextSources.ArticleTitle: ArticleTitleContext,
        }

        return CONTEXT_SOURCE_TABLE_MAPPING

    @classmethod
    def find_or_create(
        cls,
        session,
        content,
        language,
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
        stripped_content = content.strip()
        try:
            return cls.query.filter(
                cls.content_hash == text_hash(stripped_content)
            ).one()
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            try:
                new = cls(
                    stripped_content,
                    language,
                    left_ellipsis,
                    right_ellipsis,
                )
                session.add(new)
                if commit:
                    session.commit()
                return new
            except sqlalchemy.exc.IntegrityError or sqlalchemy.exc.DatabaseError:
                for i in range(10):
                    try:
                        session.rollback()
                        t = cls.query.filter(
                            cls.content_hash == text_hash(stripped_content)
                        ).one()
                        print("found text after recovering from race")
                        return t
                    except:
                        print("exception of second degree in find text..." + str(i))
                        time.sleep(0.3)
                        continue
