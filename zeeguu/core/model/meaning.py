from sqlalchemy.exc import NoResultFound

from zeeguu.core.model import db


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
# words in different languages (I still like that to be Meaning, more and more) UserMeaning to refer to a meaning and
# all the info about that particular meaning being learned by a user: too easy, level, etc.

# What if a Meaning would connect two Phrases instead of UserWords. Or just two Words. But that feels wrong...
#


class Meaning(db.Model):
    from zeeguu.core.model import db, UserWord

    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True)

    origin_id = db.Column(db.Integer, db.ForeignKey(UserWord.id), nullable=False)
    origin = db.relationship(UserWord, primaryjoin=origin_id == UserWord.id)

    translation_id = db.Column(db.Integer, db.ForeignKey(UserWord.id), nullable=False)
    translation = db.relationship(UserWord, primaryjoin=translation_id == UserWord.id)

    def __init__(self, origin: UserWord, translation: UserWord):
        self.origin = origin
        self.translation = translation

    @classmethod
    def find_or_create(
        cls,
        session,
        _origin: str,
        _origin_lang: str,
        _translation: str,
        _translation_lang: str,
    ):
        from zeeguu.core.model import UserWord, Language

        origin_lang = Language.find_or_create(_origin_lang)
        translation_lang = Language.find_or_create(_translation_lang)

        origin = UserWord.find_or_create(session, _origin, origin_lang)
        session.add(origin)

        translation = UserWord.find_or_create(session, _translation, translation_lang)
        session.add(translation)

        try:
            meaning = cls.query.filter_by(origin=origin, translation=translation).one()
        except NoResultFound:
            meaning = cls(origin, translation)
            session.add(meaning)
            session.commit()

        return meaning
