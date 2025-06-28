import random
import re
from datetime import timedelta

from zeeguu.core.bookmark_quality import quality_meaning, bad_quality_meaning
from zeeguu.core.model import Meaning
from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.meaning_rule import MeaningRule
from zeeguu.core.test.rules.phrase_rule import PhraseRule
from zeeguu.core.model.bookmark import Bookmark
from zeeguu.core.model.phrase import Phrase
from zeeguu.core.test.rules.user_word_rule import UserWordRule


class BookmarkRule(BaseRule):
    """A Rule testing class for the zeeguu.core.model.Bookmark model class.

    Creates a Bookmark object with random data and saves it to the database.
    """

    props = ["origin", "translation", "text", "date"]

    def __init__(self, user, **kwargs):
        super().__init__()
        self.bookmark = self._create_model_object(user, **kwargs)

        self.save(self.bookmark)

    def _create_model_object(self, user, force_quality=False, **kwargs):
        """
        Creates a Bookmark object with random data.

        Behind the random words, a random number is added since the Faker library does not have too many RANDOM words
        and random words get repeated whenever many random bookmarks are created. To overcome the problem of bookmarks
        with duplicate words in the database, a random number is added.

        Also, if force_quality is set (default) and the bookmark is not .quality_bookmark() the process is
        reiterated till this is true. This simplifies some of the tests

        :param user: User Object, to which the bookmark is assigned.
        :param kwargs: Holds any of the 'props' as key if a field should not be random
        :return:
        """

        bookmark = None

        while not bookmark:
            from zeeguu.core.test.rules.bookmark_context_rule import BookmarkContextRule
            from zeeguu.core.test.rules.text_rule import TextRule

            random_text = TextRule().text

            random_origin_word = self.faker.word() + str(random.random())
            random_origin_language = user.learned_language

            random_translation_word = self.faker.word() + str(random.random())
            random_translation_language = LanguageRule().random

            if Phrase.exists(
                random_origin_word, random_origin_language
            ) or Phrase.exists(random_translation_word, random_translation_language):
                return self._create_model_object(user)

            random_origin = PhraseRule(
                random_origin_word, random_origin_language
            ).phrase
            random_translation = PhraseRule(
                random_translation_word, random_translation_language
            ).phrase
            random_date = self.faker.date_time_this_month()

            source_article = random_text.article.source

            fake_bookmark_c = BookmarkContextRule(source_article.get_content()).context

            random_meaning = MeaningRule(random_origin, random_translation).meaning

            user_word = UserWordRule(user, random_meaning).user_word

            bookmark = Bookmark(
                user_word,
                source_article,
                random_text,
                random_date,
                context=fake_bookmark_c,
            )

            if force_quality and bad_quality_meaning(user_word):
                print("random bookmark was of low quality. retrying...")
                bookmark = False

        for k in kwargs:
            if k in self.props:
                setattr(bookmark, k, kwargs.get(k))

        if self._exists_in_db(bookmark):
            return self._create_model_object(user)

        return bookmark

    @staticmethod
    def _exists_in_db(obj):
        return Bookmark.exists(obj.source, obj.text, obj.context, obj.user_word)

    @staticmethod
    def __get_random_word_from_sentence(sentence):
        word_list = re.sub(r"[^\w]", " ", sentence).split()
        random_index = random.randint(0, len(word_list) - 1)
        return word_list[random_index]
