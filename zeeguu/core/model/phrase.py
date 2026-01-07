import sqlalchemy.orm
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import Computed
from wordstats import Word

from zeeguu.core.model.db import db
from zeeguu.core.model.language import Language


class Phrase(db.Model):
    __tablename__ = "phrase"

    id = db.Column(db.Integer, primary_key=True)

    language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    language = db.relationship(Language)

    content = db.Column(db.String(255), nullable=False)

    # Generated column for fast case-insensitive lookups (indexed)
    # SQLAlchemy's Computed() tells it not to include this in INSERT/UPDATE statements
    content_lower = db.Column(db.String(255), Computed("LOWER(content)"))

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
            # For multi-word phrases, use the rank of the hardest (least frequent) word
            words = self.content.split()
            if len(words) > 1:
                ranks = []
                for single_word in words:
                    try:
                        rank = Word.stats(single_word, self.language.code).rank
                        if rank is not None:
                            ranks.append(rank)
                    except:
                        # If we can't get rank for a word, treat it as very rare
                        ranks.append(self.IMPOSSIBLE_RANK)
                
                if ranks:
                    # Take the highest rank (least frequent word)
                    self.rank = max(ranks)
                else:
                    self.rank = None
            else:
                # Single word - use existing logic
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
        Convert rank to importance level for display purposes.
        Lower rank = higher importance (more frequent word)
        Returns a number between 0 and 10 for visual representation.
        """
        if self.rank is None:
            return 0
        
        # Convert rank to importance level (inverse relationship)
        # Most common words (rank 1-10) get importance 10
        # Less common words get lower importance
        if self.rank <= 10:
            return 10
        elif self.rank <= 50:
            return 9
        elif self.rank <= 100:
            return 8
        elif self.rank <= 250:
            return 7
        elif self.rank <= 500:
            return 6
        elif self.rank <= 1000:
            return 5
        elif self.rank <= 2500:
            return 4
        elif self.rank <= 5000:
            return 3
        elif self.rank <= 10000:
            return 2
        elif self.rank <= 50000:
            return 1
        else:
            return 0

    # we use this in the bookmarks.html to show the importance of a word
    def importance_level_string(self):
        b = "|"
        return b * self.importance_level()

    def ensure_rank_is_calculated(self):
        """
        Ensures that the rank is calculated for this phrase.
        If rank is None and this is a multi-word phrase, recalculate it.
        """
        if self.rank is None:
            words = self.content.split()
            if len(words) > 1:
                try:
                    ranks = []
                    for single_word in words:
                        try:
                            rank = Word.stats(single_word, self.language.code).rank
                            if rank is not None:
                                ranks.append(rank)
                        except:
                            # If we can't get rank for a word, treat it as very rare
                            ranks.append(self.IMPOSSIBLE_RANK)
                    
                    if ranks:
                        # Take the highest rank (least frequent word)
                        self.rank = max(ranks)
                        
                        # Use a separate session to avoid deadlocks
                        from zeeguu.core.model import db
                        from sqlalchemy.orm import sessionmaker
                        
                        # Create a new session for this update
                        Session = sessionmaker(bind=db.engine)
                        separate_session = Session()
                        try:
                            # Get the phrase in the separate session and update it
                            phrase_to_update = separate_session.query(Phrase).filter(Phrase.id == self.id).first()
                            if phrase_to_update:
                                phrase_to_update.rank = self.rank
                                separate_session.commit()
                        finally:
                            separate_session.close()
                except Exception:
                    pass  # Keep rank as None if we can't calculate it


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

        # if we have more than one we see if any matches the case

        matches = [each for each in ci_matches if each.content == _content]
        if len(matches) == 0:
            raise NoResultFound()

        return matches[0]

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
