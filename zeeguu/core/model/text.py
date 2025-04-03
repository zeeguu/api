import sqlalchemy.orm
import time

from sqlalchemy import UnicodeText

from zeeguu.core.util import long_hash
from zeeguu.core.model import db


class Text(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    content = db.Column(UnicodeText)
    content_hash = db.Column(db.String(64))

    def __init__(
        self,
        content,
    ):
        self.content = content
        self.content_hash = long_hash(content)

    def __repr__(self):
        return f"<NewText {self.content[:50]}>"

    def __eq__(self, other):
        return self.content_hash == other.content_hash

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
            yield UserWord.find(word, self.language)

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
        from zeeguu.core.model import Bookmark

        return Bookmark.find_all_for_text_and_user(self, user)

    def all_bookmarks_for_text(self):
        from zeeguu.core.model import Bookmark

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
        return cls.query.filter_by(id=text_id).one()

    @classmethod
    def find_or_create(
        cls,
        session,
        text,
        commit=True,
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
            return cls.query.filter(cls.content_hash == long_hash(clean_text)).one()
        except sqlalchemy.orm.exc.NoResultFound or sqlalchemy.exc.InterfaceError:
            try:
                new = cls(
                    clean_text,
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
                            cls.content_hash == long_hash(clean_text)
                        ).one()
                        print("found text after recovering from race")
                        return t
                    except Exception as e:
                        print(f"Exception: '{e}'")
                        print("exception of second degree in find NewText..." + str(i))
                        time.sleep(0.3)
                        continue
