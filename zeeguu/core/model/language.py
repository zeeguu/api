from sqlalchemy.orm.exc import NoResultFound
from datetime import datetime

from zeeguu.logging import logp

import zeeguu

from zeeguu.core.model import db


class Language(db.Model):
    __table_args__ = {"mysql_collate": "utf8_bin"}
    __tablename__ = "language"

    LANGUAGE_NAMES = {
        "sq": "Albanian",
        "ar": "Arabic",
        "zh-CN": "Chinese",
        "da": "Danish",
        "nl": "Dutch",
        "en": "English",
        "fr": "French",
        "de": "German",
        "hu": "Hungarian",
        "it": "Italian",
        "ku": "Kurdish",
        "lv": "Latvian",
        "no": "Norwegian",
        "pl": "Polish",
        "pt": "Portuguese",
        "ro": "Romanian",
        "ru": "Russian",
        "so": "Somali",
        "es": "Spanish",
        "sv": "Swedish",
        "tr": "Turkish",
        "uk": "Ukrainian",
        "vi": "Vietnamese",
        "ja": "Japanese",
        "sr": "Serbian",
        "ind": "Indonesian",
        "ur": "Urdu",
        "ta": "Tamil",
        "bn": "Bengali",
    }

    CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED = [
        "de",
        "es",
        "fr",
        "nl",
        "en",
        "it",
        "da",
        "pl",
        "sv",
        "ru",
        "no",
        "hu",
        "pt",
    ]
    CODES_OF_LANGUAGES_AVAILABLE_AS_NATIVE = [
        "da",
        "en",
        "fr",
        "nl",
        "pl",
        "ro",
        "zh-CN",
        "tr",
        "ku",
        "ar",  # arabic
        "so",  # somali
        "de",
        "sv",
        "sq",  # albanian
        "es",
        "it",
        "ja",
        "sr",
        "pt",
        "ru",
        "uk",  # ukrainian
        "vi",  # vietnamese
        "hu",
        "lv",
        "ind",
        "ur",
        "ta",
        "bn",
    ]

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(5))
    name = db.Column(db.String(255), unique=True)

    def __init__(self, code, name):
        self.code = code
        self.name = name

    def __repr__(self):
        return "<Language %r>" % self.code

    def __eq__(self, other):
        return self.code == other.code or self.name == other.name

    def as_dictionary(self):

        return dict(
            id=self.id,
            code=self.code,
            language=self.name,
        )

    @classmethod
    def default_learned(cls):
        return cls.find_or_create("de")

    @classmethod
    def default_native_language(cls):
        return cls.find_or_create("en")

    @classmethod
    def native_languages(cls):
        return [
            Language.find_or_create(code)
            for code in cls.CODES_OF_LANGUAGES_AVAILABLE_AS_NATIVE
        ]

    @classmethod
    def available_languages(cls):
        return [
            Language.find_or_create(code)
            for code in cls.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED
        ]

    @classmethod
    def find(cls, code):
        result = cls.query.filter(Language.code == code).one()
        return result

    @classmethod
    def find_or_create(cls, language_code):
        # due to the limitations of the WTFFOrms, the zh-CN can't be used in the UI...
        if language_code == "cn":
            language_code = "zh-CN"

        try:
            language = cls.find(language_code)

        except NoResultFound:
            language = cls(language_code, cls.LANGUAGE_NAMES[language_code])
            db.session.add(language)
            db.session.commit()

        return language

    @classmethod
    def all(cls):
        return cls.query.filter().order_by(Language.name).all()

    @classmethod
    def find_by_id(cls, i):
        return cls.query.filter(Language.id == i).one()

    def get_articles(
        self, after_date=None, most_recent_first=False, easiest_first=False
    ):
        from zeeguu.core.model import Article

        if hasattr(Language, "cached_articles") and (
            self.cached_articles.get(self.id, None)
        ):
            logp(
                f"found {len(Language.cached_articles[self.id])} cached articles for {self.name}"
            )
            all_ids = Language.cached_articles[self.id]
            return Article.query.filter(Article.id.in_(all_ids)).all()

        if not hasattr(Language, "cached_articles"):
            Language.cached_articles = {}

        logp("computing and caching the articles for language: " + self.name)
        Language.cached_articles[self.id] = [
            each.id
            for each in self._get_articles(after_date, most_recent_first, easiest_first)
        ]

        all_ids = Language.cached_articles[self.id]
        return Article.query.filter(Article.id.in_(all_ids)).all()

    def _get_articles(
        self, after_date=None, most_recent_first=False, easiest_first=False
    ):
        """

            Articles for this language from the article DB

        :param limit:
        :param after_date:
        :param most_recent_first:
        :param easiest_first:
        :return:
        """

        from zeeguu.core.model import Article

        if not after_date:
            after_date = datetime(2001, 1, 1)

        try:
            q = (
                Article.query.filter(Article.language == self)
                .filter(Article.broken == 0)
                .filter(Article.published_time >= after_date)
                .filter(Article.word_count > Article.MINIMUM_WORD_COUNT)
            )

            if most_recent_first:
                q = q.order_by(Article.published_time.desc())
            if easiest_first:
                q = q.order_by(Article.fk_difficulty)

            return q.limit(10000)

        except Exception as e:
            raise (e)
            return None

    @classmethod
    def all_reading_for_user(cls, user):
        """
            this used to allow multiple languages for reading;
            currently it simply returns the learned language
        :param user:
        :return:
        """

        return [user.learned_language]
