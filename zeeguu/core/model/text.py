import re

import sqlalchemy.orm
import time
from zeeguu.core.model import Article

from zeeguu.core.util import text_hash
from zeeguu.core.model.language import Language
from zeeguu.core.model.url import Url
from zeeguu.core.model.phrase import Phrase

from zeeguu.core.model.db import db


class Text(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    # This used to be db.Column(db.String(64000), but that caused the following MySQL error: sqlalchemy.exc.OperationalError: (MySQLdb.OperationalError) (1074, "Column length too big for column 'content' (max = 21845); use BLOB or TEXT instead")
    content = db.Column(db.Text())
    content_hash = db.Column(db.String(64))

    language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    language = db.relationship(Language)

    url_id = db.Column(db.Integer, db.ForeignKey(Url.id))
    url = db.relationship(Url)

    article_id = db.Column(db.Integer, db.ForeignKey(Article.id))
    article = db.relationship(Article)

    """
     The coordinates of the first token of the text from its' source.
     This can be an article, in which case in_content is true, or some other source, 
    which isn't the content where this will be false. At the moment, this is used for 
    text from titles.
     In case a user changes the context, so that this is not found in the text, all the 
    values will be set to null. This means that the bookmark will no longer be highligted,
    in the article, but it will still be found within the text.

    - left/right_ellipsis, is set based on when the context is created so that in exercises
    we can render the elipsis without having to create it as a token.
    """
    paragraph_i = db.Column(db.Integer)
    sentence_i = db.Column(db.Integer)
    token_i = db.Column(db.Integer)
    in_content = db.Column(db.Boolean)
    left_ellipsis = db.Column(db.Boolean)
    right_ellipsis = db.Column(db.Boolean)

    def __init__(
        self,
        content,
        language,
        url,
        article,
        paragraph_i=None,
        sentence_i=None,
        token_i=None,
        in_content=None,
        left_ellipsis=None,
        right_ellipsis=None,
    ):
        self.content = content
        self.language = language
        self.url = url
        self.content_hash = text_hash(content)
        self.article = article
        self.paragraph_i = paragraph_i
        self.sentence_i = sentence_i
        self.token_i = token_i
        self.in_content = in_content
        self.left_ellipsis = left_ellipsis
        self.right_ellipsis = right_ellipsis

    def __repr__(self):
        return f"<Text {self.content}>"

    def get_content(self):
        return self.content

    def update_content(self, new_content):
        self.content = new_content
        self.content_hash = text_hash(new_content)

    def url(self):
        # legacy; some texts don't have an article associated with them
        if not self.article:
            return ""

        if not self.article.url:
            return ""

        return self.article.url.as_string()

    def words(self):
        for word in re.split(re.compile("[^\\w]+", re.U), self.content):
            yield Phrase.find(word, self.language)

    def shorten_word_context(self, given_word, max_word_count):
        # shorter_text = ""
        limited_words = []

        words = (
            self.content.split()
        )  # ==> gives me a list of the words ["these", "types", ",", "the"]
        word_count = len(words)

        if word_count <= max_word_count:
            return self.content

        for i in range(0, max_word_count):
            limited_words.append(words[i])  # lista cu primele max_length cuvinte
        shorter_text = " ".join(limited_words)  # string cu primele 'max_word_count' cuv

        # sometimes the given_word does not exist in the text.
        # in that case return a text containing max_length words
        if given_word not in words:
            return shorter_text

        if words.index(given_word) <= max_word_count:
            return shorter_text

        for i in range(max_word_count + 1, words.index(given_word) + 1):
            limited_words.append(words[i])
        shorter_text = " ".join(limited_words)

        return shorter_text

    def all_bookmarks(self, user):
        # TODO: Tiago, Delete after Text is deleted
        from zeeguu.core.model.bookmark import Bookmark

        return Bookmark.find_all_for_text_and_user(self, user)

    def all_bookmarks_for_text(self):
        from zeeguu.core.model.bookmark import Bookmark

        return Bookmark.query.join(Text).filter(Bookmark.text_id == self.id).all()

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
    def find_by_id(cls, text_id):
        try:
            return cls.query.filter_by(id=text_id).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    @classmethod
    def find_or_create(
        cls,
        session,
        text,
        language,
        url,
        article,
        paragraph_i,
        sentence_i,
        token_i,
        in_content,
        left_elipsis,
        right_elipsis,
    ):
        """
        :param text: string
        :param language: Language (object)
        :param url: Url (object)
        :return:
        """
        # we ended up with a bunch of duplicates in the
        # db because of some trailing spaces difference
        # i guess the clients sometimes clean up the context
        # and some other times don't.
        # we fix it here now

        clean_text = text.strip()
        try:
            return (
                cls.query.filter(cls.content_hash == text_hash(clean_text))
                .filter(cls.article == article)
                .one()
            )
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            try:
                new = cls(
                    clean_text,
                    language,
                    url,
                    article,
                    paragraph_i,
                    sentence_i,
                    token_i,
                    in_content,
                    left_elipsis,
                    right_elipsis,
                )
                session.add(new)
                session.commit()
                return new
            except sqlalchemy.exc.IntegrityError or sqlalchemy.exc.DatabaseError:
                for i in range(10):
                    try:
                        session.rollback()
                        t = cls.query.filter(
                            cls.content_hash == text_hash(clean_text)
                        ).one()
                        print("found text after recovering from race")
                        return t
                    except:
                        print("exception of second degree in find text..." + str(i))
                        time.sleep(0.3)
                        continue
                    break
