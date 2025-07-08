from enum import Enum

from sqlalchemy.exc import NoResultFound

from zeeguu.core.model.db import db
from zeeguu.core.model.phrase import Phrase
from zeeguu.logging import logp


# I've thought a lot about what could be alternative names for this concept
# 1. WordPair - but it seems too trivial to say you're learning word pairs
# 2. LexicalUnit - sounds too fancy
# 3. PhrasePair - sometimes there are also words
# 4. Translation - it is a translation. this is the most correct. the bookmark is a translation in context.
# however, from the learner's point of view a word indeed can have multiple translations, in multiple contexts.
# and they are not meanings really, there could be two translations with the same meaning...
# I guess if I added a vector embedding of the two
# problem with word meaning is that ... we can have an expression meaning too in here
# also, there's imprecision... sometimes the translations are wrong :(

# what does the scheduler work with?
# scheduling a word-pair ... that is fine.
# sheduling a phrase-pair... that sounds awkward
# scheduing a lexicalUnit... fancy
# scheduling a translation for practice... that is strange too

# also, the italian word "amore" has multiple meanings. that is the most natural way of talking about it.
# however, the problem is that what we get from translate might not always be a real meaning;
# I guess we could have something that would validate some meanings? could we have something that would
# also match words with meanings? we could start doing statistics on the most frequent meanings of a given word

# In an ideal world, when one says: "don't show this word again", we could pop up a confirmation asking
# "Do you mean not this particular meaning, or none of the meanings alltogether?" and maybe sho all the meanings
# and let the user select meanings... but remember, the whole point of zeeguu is that you encounter words on the
# net, translate them, and then choose to work on learning that particular meaning.

# what if i use: TranslationEvent ... to record the translation, Translation to save the mapping between two
# words in different languages (I still like that to be Meaning, more and more) UserWord to refer to a meaning and
# all the info about that particular meaning being learned by a user: too easy, level, etc.

# What if a Meaning would connect two Phrases instead of UserWords. Or just two Words. But that feels wrong...
#


class MeaningFrequency(Enum):
    """
    Categorizes how frequently a particular meaning is used for a word.
    Used to help learners prioritize which meanings to learn first.
    """

    UNIQUE = "unique"  # Only meaning of the word
    COMMON = "common"  # Primary or very widespread usage
    UNCOMMON = "uncommon"  # Infrequent usage, not essential for basic communication
    RARE = "rare"  # Specialized, archaic, or context-specific


class PhraseType(Enum):
    """
    Categorizes the type of phrase/expression this meaning represents.
    Helps with learning strategies and exercise generation.
    """

    SINGLE_WORD = "single_word"  # Individual word: "cat", "run", "beautiful"
    COLLOCATION = "collocation"  # Word combinations: "strong coffee", "heavy rain"
    IDIOM = "idiom"  # Idiomatic expressions: "break the ice", "piece of cake"
    EXPRESSION = "expression"  # Common phrases: "how are you?", "thank you"
    ARBITRARY_MULTI_WORD = "multi_word"  # Arbitrary multi-word selection: "the cat on the", "walked slowly towards"


class Meaning(db.Model):

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    origin_id = db.Column(db.Integer, db.ForeignKey(Phrase.id), nullable=False)
    origin = db.relationship(Phrase, primaryjoin=origin_id == Phrase.id)

    translation_id = db.Column(db.Integer, db.ForeignKey(Phrase.id), nullable=False)
    translation = db.relationship(Phrase, primaryjoin=translation_id == Phrase.id)

    frequency = db.Column(
        db.Enum(MeaningFrequency),
        nullable=True,  # Nullable for backward compatibility
        default=None,
        comment="How frequently this particular meaning is used",
    )

    frequency_manually_validated = db.Column(
        db.Boolean,
        nullable=True,
        default=False,
        comment="Whether the frequency has been manually validated by a human",
    )

    phrase_type = db.Column(
        db.Enum(PhraseType),
        nullable=True,
        default=None,
        comment="Type of phrase/expression (single word, idiom, collocation, etc.)",
    )

    phrase_type_manually_validated = db.Column(
        db.Boolean,
        nullable=True,
        default=False,
        comment="Whether the phrase type has been manually validated by a human",
    )

    def __init__(
        self, origin: Phrase, translation: Phrase, frequency=None, phrase_type=None
    ):
        self.origin = origin
        self.translation = translation
        self.frequency = frequency
        self.phrase_type = phrase_type

    def __repr__(self):
        freq_str = f", frequency={self.frequency.value}" if self.frequency else ""
        return (
            f"Meaning(origin={self.origin}, translation={self.translation}{freq_str})"
        )

    @classmethod
    def find_or_create(
        cls,
        session,
        _origin: str,
        _origin_lang: str,
        _translation: str,
        _translation_lang: str,
        frequency=None,
        phrase_type=None,
    ):
        from zeeguu.core.model import Phrase, Language

        origin_lang = Language.find_or_create(_origin_lang)
        translation_lang = Language.find_or_create(_translation_lang)

        origin = Phrase.find_or_create(session, _origin, origin_lang)
        session.add(origin)

        translation = Phrase.find_or_create(session, _translation, translation_lang)
        session.add(translation)

        try:
            meaning = cls.query.filter_by(origin=origin, translation=translation).one()
            # Update frequency or phrase_type if provided and different
            updated = False
            if frequency and meaning.frequency != frequency:
                meaning.frequency = frequency
                updated = True
            if phrase_type and meaning.phrase_type != phrase_type:
                meaning.phrase_type = phrase_type
                updated = True
            if updated:
                session.add(meaning)
                session.commit()

            # Also classify if existing meaning lacks classification
            # Skip classification for phrases longer than 3 words to save API costs
            word_count = len(meaning.origin.content.split())
            if (not meaning.frequency or not meaning.phrase_type) and word_count <= 3:
                cls._classify_meaning_async(meaning.id)
        except NoResultFound:
            meaning = cls(origin, translation, frequency, phrase_type)
            session.add(meaning)
            session.commit()

            # Classify meaning asynchronously if not already classified
            # Skip classification for phrases longer than 3 words to save API costs
            word_count = len(meaning.origin.content.split())

            if (not meaning.frequency or not meaning.phrase_type) and word_count <= 3:
                cls._classify_meaning_async(meaning.id)

        return meaning

    @classmethod
    def _classify_meaning_async(cls, meaning_id):
        """
        Classify meaning frequency and phrase type asynchronously.
        """
        import threading
        from zeeguu.core.model.meaning_frequency_classifier import (
            MeaningFrequencyClassifier,
        )

        def classify_in_background():
            try:

                # Import Flask app to create proper application context
                import zeeguu.core

                app = zeeguu.core.app

                # Create application context for this thread
                with app.app_context():

                    # Import db within the app context
                    from zeeguu.core.model import db

                    # Get meaning using the thread-safe session
                    meaning = db.session.query(cls).get(meaning_id)

                    if meaning and (not meaning.frequency or not meaning.phrase_type):
                        try:
                            classifier = MeaningFrequencyClassifier()
                            classifier.classify_and_update_meaning(meaning, db.session)
                            logp(
                                f">>> Successfully classified meaning {meaning.origin.content} as {meaning.frequency},{meaning.phrase_type} in background"
                            )
                        except ValueError as ve:
                            logp(
                                f"Classification disabled for meaning {meaning_id}: {str(ve)}"
                            )
                        except Exception as ce:
                            logp(
                                f"Classification failed for meaning {meaning_id}: {str(ce)}"
                            )
                    else:
                        print(
                            f">>>> Meaning {meaning_id} already classified or not found"
                        )

            except Exception as e:
                logp(f"Error classifying meaning {meaning_id} in background: {str(e)}")

        # Start background thread
        thread = threading.Thread(target=classify_in_background)
        thread.daemon = True  # Thread will die when main program exits
        thread.start()
        print(f">>>> Classification thread started for meaning {meaning_id}")

    @classmethod
    def exists(cls, origin, translation):
        try:
            cls.query.filter_by(origin=origin, translation=translation).one()
            return True
        except NoResultFound:
            return False
