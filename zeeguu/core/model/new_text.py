import sqlalchemy.orm
import time

from sqlalchemy import UnicodeText

from zeeguu.core.util import long_hash
from zeeguu.core.model import db


class NewText(db.Model):
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

    def update_content(self, new_content):
        self.content = new_content
        self.content_hash = long_hash(new_content)

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
