import sqlalchemy.orm
import zeeguu_core

from zeeguu_core.model.language import Language

db = zeeguu_core.db


class WordForm(db.Model):
    __tablename__ = 'word_form'
    __table_args__ = {'mysql_collate': 'utf8_bin'}

    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(255), nullable =False, index = True)

    language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    language = db.relationship(Language)
    db.UniqueConstraint(word, language_id)

    def __init__(self, word, language):
        self.word = word
        self.language = language

    @classmethod
    def find_or_create(cls, word, language):
        # TODO: we need a general policy of lowercasing words... 
        word = word.lower()
        try:
            return (cls.query.filter(cls.word == word)
                             .filter(cls.language == language)
                             .one())
        except sqlalchemy.orm.exc.NoResultFound:
            return cls(word, language)

    # @classmethod
    # def find_all(cls,language):
    #     return cls.query.filter(cls.language == language
    #     ).all()

    # @classmethod
    # def words_list(cls):
    #     words_list = []
    #     for word in cls.find_all():
    #          words_list.append(word.word)
    #     return words_list