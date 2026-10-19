import random
from unittest import mock

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Query

from wordstats.loading_from_hermit import load_language_from_hermit

from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.phrase_rule import PhraseRule
from zeeguu.core.test.rules.meaning_rule import MeaningRule
from zeeguu.core.test.rules.user_rule import UserRule
from zeeguu.core.model import Phrase, UserWord
from zeeguu.core.model.db import db


class UserWordTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()

    def test_find(self):
        phrase_should_be = PhraseRule().phrase
        phrase_to_check = Phrase.find(
            phrase_should_be.content, phrase_should_be.language
        )

        assert phrase_to_check == phrase_should_be

    def test_find_or_create(self):
        random_word = self.faker.word()
        random_language = LanguageRule().random
        phrase_not_in_db = Phrase(random_word, random_language)
        phrase_created = Phrase.find_or_create(db.session, random_word, random_language)

        assert phrase_created == phrase_not_in_db

    def test_find_all(self):
        list_random_phrases = [PhraseRule().phrase for _ in range(random.randint(2, 5))]
        list_retrieved = Phrase.find_all()

        assert all([word in list_retrieved for word in list_random_phrases])

    def test_exists(self):
        phrase_in_db = PhraseRule().phrase
        assert Phrase.exists(phrase_in_db.content, phrase_in_db.language)

    def test_find_or_create_loses_the_insert_race(self):
        # A double tap: the other request inserts the row after this one's
        # lookup has already missed it.
        user = UserRule().user
        meaning = MeaningRule().meaning
        winner = UserWord.find_or_create(db.session, user, meaning)

        real_one = Query.one
        lookups = []

        def first_lookup_misses(query):
            lookups.append(query)
            if len(lookups) == 1:
                raise NoResultFound()
            return real_one(query)

        with mock.patch.object(Query, "one", first_lookup_misses):
            loser = UserWord.find_or_create(db.session, user, meaning)

        assert loser.id == winner.id
        assert UserWord.query.filter_by(user=user, meaning=meaning).count() == 1

    def __get_random_word_stats(self):
        random_language = LanguageRule().random
        language_stats = load_language_from_hermit(random_language.code)
        return random.choice(list(language_stats.word_info_dict.items()))
