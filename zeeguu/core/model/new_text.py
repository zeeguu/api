from sqlalchemy import UnicodeText

from zeeguu.core.util import long_hash
from zeeguu.core.model.db import db
from zeeguu.core.model.race_safe import find_or_create


class NewText(db.Model):
    __table_args__ = (
        # Declared so create_all (the test DB) has it too; prod's comes from
        # tools/migrations/25-02-28--01-new-content-tables copy.sql
        db.UniqueConstraint("content_hash", name="HASH_INDEX"),
        {"mysql_collate": "utf8_bin"},
    )

    id = db.Column(db.Integer, primary_key=True)

    content = db.Column(UnicodeText)
    content_hash = db.Column(db.String(64))

    def __init__(
        self,
        content,
    ):
        self.content = content
        self.content_hash = long_hash(content)

    def get_content(self):
        return self.content

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
        # Two requests saving the same text can race here; the unique
        # content_hash lets one insert through and race_safe.find_or_create
        # recovers the other.
        return find_or_create(
            session,
            cls,
            {"content_hash": long_hash(clean_text)},
            lambda: cls(clean_text),
            commit=commit,
        )
