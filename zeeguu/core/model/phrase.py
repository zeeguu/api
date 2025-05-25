import sqlalchemy.orm
from sqlalchemy.orm.exc import NoResultFound
from wordstats import Word

from zeeguu.core.model import db
from zeeguu.core.model.language import Language


class Phrase(db.Model):
    __tablename__ = "phrase"

    id = db.Column(db.Integer, primary_key=True)

    language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    language = db.relationship(Language)

    content = db.Column(db.String(255), nullable=False)

    rank = db.Column(db.Integer)

    db.UniqueConstraint(content, language_id)

    IMPORTANCE_LEVEL_STEP = 1000
    IMPOSSIBLE_RANK = 1000000
    IMPOSSIBLE_IMPORTANCE_LEVEL = IMPOSSIBLE_RANK / IMPORTANCE_LEVEL_STEP

    def __init__(self, word, language):
        self.content = word
        self.language = language

        # TODO: Performance
        try:
            self.rank = Word.stats(self.content, self.language.code).rank
        except FileNotFoundError:
            self.rank = None
        except Exception:
            self.rank = None

    def __repr__(self):
        return f"<@Phrase {self.content} {self.language_id} {self.rank}>"

    def __str__(self):
        return f"<@Phrase {self.content} {self.language_id} {self.rank}>"

    def __eq__(self, other):
        return self.content == other.content and self.language == other.language

    def importance_level(self):
        """
            Note that this code will break if the wordstats throws an exception,
            which could happen in case the language is inexistent…
            but this should not happen.

            Note that the importance level is float

        :return: number between 0 and 10 as returned by the wordstats module
        """
        stats = Word.stats(self.content, self.language.code)
        return int(stats.importance)

    # we use this in the bookmarks.html to show the importance of a word
    def importance_level_string(self):
        b = "|"
        return b * self.importance_level()

    @classmethod
    def find(cls, _content: str, language: Language):
        # The DB does a case insensitive search so it will return both Pee and pee
        # Here we get all the results from the DB, and we do the equality test here in python
        # This has the downside that it will represent the same word twice :( Piss and piss.
        # Equally, if case insensitive would find it, now we ensure that
        ci_matches = (
            cls.query.filter(cls.content == _content)
            .filter(cls.language == language)
            .all()
        )

        if len(ci_matches) == 0:
            raise NoResultFound()

        if len(ci_matches) == 1:
            return ci_matches[0]

        # if we have more than one we return the one that matches the case
        return [each for each in ci_matches if each.content == _content][0]

    @classmethod
    def find_or_create(cls, session, _word: str, language: Language):
        try:
            return cls.find(_word, language)
        except sqlalchemy.orm.exc.NoResultFound:
            try:
                new = cls(_word, language)
                session.add(new)
                session.commit()
                return new
            except sqlalchemy.exc.IntegrityError:
                for _ in range(10):
                    try:
                        session.rollback()
                        w = cls.find(_word, language)
                        print("successfully avoided race condition. nice! ")
                        return w
                    except sqlalchemy.orm.exc.NoResultFound:
                        import time

                        time.sleep(0.3)
                        continue
                    break

    @classmethod
    def find_all(cls):
        return cls.query.all()

    @classmethod
    def exists(cls, content, language):
        try:
            cls.query.filter_by(language=language, content=content).one()
            return True
        except NoResultFound:
            return False
