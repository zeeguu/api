from sqlalchemy.orm import relationship
from zeeguu.core.model.url import Url
from zeeguu.core.model.language import Language
from zeeguu.core.model.new_topic import NewTopic
from zeeguu.core.util import remove_duplicates_keeping_order
import sqlalchemy
import string
from collections import Counter

from zeeguu.core.model import db


class UrlKeyword(db.Model):
    """
    These are words extracted from the URL that can be used as keywords
    for the New Topic Table. Each keyword is associated with a language,
    as some language might have the same word for 2 different topics.

    We have a url keyword entry even if it is not mapped on a topic.
    So pretty much, every time we find a URL keyword we put it in here
    And we also map it to the article.


    """

    EXCLUDE_TOPICS = set(
        [
            "news",
            "i",
            "nyheter",
            "article",
            "nieuws",
            "aktuell",
            "artikel",
            "wiadomosci",
            "actualites",
            "cronaca",
            "nyheder",
            "jan",
            "feb",
            "mar",
            "apr",
            "may",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
        ]
    )

    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "url_keyword"

    id = db.Column(db.Integer, primary_key=True)

    language_id = db.Column(db.Integer, db.ForeignKey(Language.id))
    language = relationship(Language)

    new_topic_id = db.Column(db.Integer, db.ForeignKey(NewTopic.id))
    new_topic = relationship(NewTopic)

    keyword = db.Column(db.String(45))
    articles = relationship("ArticleUrlKeywordMap", back_populates="url_keyword")

    def __init__(self, keyword: str, language: Language, new_topic: NewTopic = None):

        self.language = language
        self.new_topic = new_topic
        self.keyword = keyword

    def __str__(self):
        return f"Topic keyword ({self.keyword})"

    def get_keyword(self):
        return self.keyword

    __repr__ = __str__

    @classmethod
    def find_or_create(
        cls, session, keyword, language: Language, new_topic: NewTopic = None
    ):
        try:
            return (
                cls.query.filter(cls.keyword == keyword)
                .filter(cls.language_id == language.id)
                .one()
            )
        except sqlalchemy.orm.exc.NoResultFound:
            new = cls(keyword, language, new_topic)
            session.add(new)
            session.commit()
            return new

    @classmethod
    def find_first_by_keyword(cls, keyword):
        return cls.query.filter(cls.keyword == keyword).all()[0]

    @classmethod
    def find_all_by_keyword(cls, keyword):
        return cls.query.filter(cls.keyword == keyword).all()

    @classmethod
    def with_id(cls, i):
        return (cls.query.filter(cls.id == i)).one()

    @classmethod
    def topic_filter(cls, topic: str) -> bool:
        if topic == "":
            return False
        if topic.isnumeric():
            return False
        if len(topic) > 20:
            return False
        if Counter(topic)["-"] > 2:
            # If there is more than two - in the topic it's probably a title
            return False
        return True

    @classmethod
    def is_non_word(cls, word: str) -> bool:
        n_upper = 0
        n_numbers = 0
        n_symbols = 0
        n_vowels = 0
        upper_in_middle = False
        for i, c in enumerate(word):
            if c.isupper():
                n_upper += 1
                if not upper_in_middle and i > 0:
                    if word[i - 1] != " ":
                        upper_in_middle = True
            if c in string.punctuation:
                n_symbols += 1
            if c in "aeiuo":
                n_vowels += 1
            if c.isnumeric():
                n_numbers += 1
        return (
            n_upper < 2
            and n_symbols == 0
            and n_vowels > 0
            and not upper_in_middle
            and n_numbers == 0
        )

    @classmethod
    def get_url_keywords_from_url(cls, url: Url):
        try:
            path = str(url.path)
            topic_k = filter(cls.topic_filter, path.split("/"))
            topic_k = filter(
                cls.is_non_word, map(lambda x: x.replace("-", " "), topic_k)
            )
            topic_k = map(lambda x: x.lower().strip(), topic_k)
        except Exception as e:
            print(f"Failed for url '{url.path}', with: '{e}'")
            return None
        return remove_duplicates_keeping_order(topic_k)
