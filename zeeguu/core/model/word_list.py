import sqlalchemy

from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language
from zeeguu.core.util.time import server_now


class WordList(db.Model):
    """
    A curated list of words and expressions in one language: an exam list
    (PD3), a basic-vocabulary list, later lists a teacher or a learner makes.

    What it is for: highlighting its entries where they occur in what the
    learner reads, so the learner meets them in real sentences and picks the
    ones to study, and ranking articles by how many entries they contain.
    Entries are not scheduled for study by being on a list.

    The entries are plain text for now, as the list's author wrote them.
    Linking them to Phrase/Meaning comes when something needs it (a learner
    saving an entry, counting which entries a learner already knows).
    """

    __tablename__ = "word_list"
    __table_args__ = (
        # Named as in the migration, so metadata and the database agree
        sqlalchemy.UniqueConstraint("name", "language_id", name="name"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_bin"},
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    # The language of the entries
    language_id = db.Column(db.Integer, db.ForeignKey(Language.id), nullable=False)
    language = db.relationship(Language, foreign_keys=[language_id])
    # The language of the entries' translations, when they have any
    translation_language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    translation_language = db.relationship(Language, foreign_keys=[translation_language_id])
    # Where the list came from, for whoever wonders later
    origin = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=server_now)

    entries = db.relationship(
        "WordListEntry",
        back_populates="word_list",
        order_by="WordListEntry.position",
        cascade="all, delete-orphan",
    )

    @classmethod
    def find(cls, name, language):
        return cls.query.filter_by(name=name, language_id=language.id).first()

    def import_entries(self, rows):
        """
        Make the list's entries these rows, in this order. `rows`: dicts with
        "phrase" and optionally "translation", "example", "section".

        Matched to existing entries by phrase, so importing a corrected file
        again updates entries in place (their ids stay) instead of duplicating
        them; entries no longer in the file are removed. Returns (added,
        updated, removed) counts. Does not commit.
        """
        existing = {e.phrase: e for e in self.entries}
        seen = set()
        added = updated = 0
        for position, row in enumerate(rows):
            phrase = row["phrase"].strip()
            if not phrase or phrase in seen:
                continue
            seen.add(phrase)
            values = dict(
                position=position,
                section=(row.get("section") or "").strip() or None,
                translation=(row.get("translation") or "").strip() or None,
                example=(row.get("example") or "").strip() or None,
            )
            entry = existing.get(phrase)
            if entry is None:
                self.entries.append(WordListEntry(phrase=phrase, **values))
                added += 1
            elif any(getattr(entry, k) != v for k, v in values.items()):
                for k, v in values.items():
                    setattr(entry, k, v)
                updated += 1
        removed = [e for phrase, e in existing.items() if phrase not in seen]
        for entry in removed:
            self.entries.remove(entry)
        return added, updated, len(removed)

    def as_dictionary(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "language": self.language.code,
            "translation_language": self.translation_language.code if self.translation_language else None,
            "entry_count": len(self.entries),
        }


class WordListEntry(db.Model):
    """
    One word or expression on a WordList, as the list's author wrote it
    ("En konsekvens af"), with its translation and an example sentence when
    the list gives them, and the section of the list it sits in.
    """

    __tablename__ = "word_list_entry"
    __table_args__ = (
        sqlalchemy.UniqueConstraint("word_list_id", "phrase", name="word_list_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_bin"},
    )

    id = db.Column(db.Integer, primary_key=True)
    word_list_id = db.Column(db.Integer, db.ForeignKey(WordList.id, ondelete="CASCADE"), nullable=False)
    word_list = db.relationship(WordList, back_populates="entries")
    # Order within the list, so it reads as its author arranged it
    position = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(255))
    phrase = db.Column(db.String(255), nullable=False)
    translation = db.Column(db.String(255))
    example = db.Column(db.Text)

    def as_dictionary(self):
        return {
            "id": self.id,
            "position": self.position,
            "section": self.section,
            "phrase": self.phrase,
            "translation": self.translation,
            "example": self.example,
        }
