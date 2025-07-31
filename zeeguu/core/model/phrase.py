import sqlalchemy.orm
from sqlalchemy.orm.exc import NoResultFound
from wordstats import Word

from zeeguu.core.model.db import db
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
            Note that this code will break if the wordstats throws an exception,
            which could happen in case the language is inexistent…
            but this should not happen.

            Note that the importance level is float

        :return: number between 0 and 10 as returned by the wordstats module
        """
        try:
            # For multi-word phrases, use the importance of the hardest (least frequent) word
            words = self.content.split()
            if len(words) > 1:
                min_importance = 10  # Start with max importance
                for single_word in words:
                    try:
                        stats = Word.stats(single_word, self.language.code)
                        if stats.importance < min_importance:
                            min_importance = stats.importance
                    except:
                        # If we can't get stats for a word, treat it as very rare (low importance)
                        min_importance = 0
                return int(min_importance)
            else:
                # Single word - use existing logic
                stats = Word.stats(self.content, self.language.code)
                return int(stats.importance)
        except:
            return 0  # Default to lowest importance if error

    # we use this in the bookmarks.html to show the importance of a word
    def importance_level_string(self):
        b = "|"
        return b * self.importance_level()

    def ensure_rank_is_calculated(self):
        """
        Ensures that the rank is calculated for this phrase.
        If rank is None and this is a multi-word phrase, recalculate it.
        """
        from zeeguu.logging import log
        
        log(f"ensure_rank_is_calculated called for phrase '{self.content}', current rank: {self.rank}")
        
        if self.rank is None:
            words = self.content.split()
            log(f"Phrase '{self.content}' split into words: {words}")
            
            if len(words) > 1:
                try:
                    ranks = []
                    for single_word in words:
                        try:
                            rank = Word.stats(single_word, self.language.code).rank
                            log(f"Word '{single_word}' has rank: {rank}")
                            if rank is not None:
                                ranks.append(rank)
                        except Exception as e:
                            # If we can't get rank for a word, treat it as very rare
                            log(f"Failed to get rank for word '{single_word}': {e}")
                            ranks.append(self.IMPOSSIBLE_RANK)
                    
                    log(f"All ranks collected for '{self.content}': {ranks}")
                    
                    if ranks:
                        # Take the highest rank (least frequent word)
                        self.rank = max(ranks)
                        log(f"Calculated rank for '{self.content}': {self.rank}")
                        
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
                                log(f"Successfully saved rank {self.rank} for phrase '{self.content}'")
                        finally:
                            separate_session.close()
                except Exception as e:
                    log(f"Error calculating rank for phrase '{self.content}': {e}")
                    pass  # Keep rank as None if we can't calculate it
            else:
                log(f"Phrase '{self.content}' is single word, skipping rank calculation")
        else:
            log(f"Phrase '{self.content}' already has rank {self.rank}, skipping calculation")


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
