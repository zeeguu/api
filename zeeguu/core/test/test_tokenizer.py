from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.tokenization import tokenize_text_flat_array
from zeeguu.core.test.rules.language_rule import LanguageRule
import os
import random


class TokenizationTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.en_lang = LanguageRule.get_or_create_language("en")
        self.es_lang = LanguageRule.get_or_create_language("es")
        self.de_lang = LanguageRule.get_or_create_language("de")
        self.fr_lang = LanguageRule.get_or_create_language("fr")
        self.da_lang = LanguageRule.get_or_create_language("da")
        self.it_lang = LanguageRule.get_or_create_language("it")

    @classmethod
    def _generate_random_numbers(cls, n=1000, max_range=100000):
        random.seed(0)
        random_numbers = []
        for _ in range(n):
            number = random.random() * max_range
            precision = random.randint(0, 10)
            rounded_number = round(number, precision)
            str_rounded_number = str(rounded_number)
            whole, decimal = str_rounded_number.split(".")
            # About half of the times generate a number with a
            # comma between three units like 1,385.231
            if len(whole) > 3 and random.random() > 0.5:
                with_comma = ""
                counter = 0
                for c in whole[::-1]:
                    if counter == 3:
                        with_comma += ","
                        counter = 0
                    with_comma += c
                    counter += 1
                whole = with_comma[::-1]
            str_rounded_number = f"{whole}.{decimal}"
            if precision == 0:
                rounded_number = int(rounded_number)
                str_rounded_number = whole
            random_numbers.append(str_rounded_number)
        return random_numbers

    @classmethod
    def _load_example_file(cls, filename):
        path_to_file = os.path.join(
            "/Zeeguu-API", "zeeguu", "core", "test", "test_data", filename
        )
        example_list = []
        with open(path_to_file, "r", encoding="utf-8") as f:
            # Skip the first line.
            example_list = [l.strip() for i, l in enumerate(f.readlines()) if i != 0]
        return example_list

    def test_english_sentence_1(self):
        example_sentence = "This is a test sentence."
        tokens = tokenize_text_flat_array(example_sentence, self.en_lang, False)
        assert ["This", "is", "a", "test", "sentence", "."] == [t.text for t in tokens]
        assert tokens[-1].is_punctuation
        assert tokens[0].is_sent_start

    def test_english_sentence_2(self):
        sent = "I have (parentheses) in this sentence."
        tokens = tokenize_text_flat_array(sent, self.en_lang, False)
        assert [
            "I",
            "have",
            "(",
            "parentheses",
            ")",
            "in",
            "this",
            "sentence",
            ".",
        ] == [t.text for t in tokens]
        assert tokens[2].is_left_punct
        assert tokens[4].is_right_punct
        assert tokens[0].is_sent_start
        assert tokens[-1].is_punctuation

    def test_english_sentence_3(self):
        sent = (
            "It's sentence one. Sentence two is here. Sentence three is the last one."
        )
        tokens = tokenize_text_flat_array(sent, self.en_lang, False)
        assert [
            "It",
            "'s",
            "sentence",
            "one",
            ".",
            "Sentence",
            "two",
            "is",
            "here",
            ".",
            "Sentence",
            "three",
            "is",
            "the",
            "last",
            "one",
            ".",
        ] == [t.text for t in tokens]
        assert tokens[-1].is_punctuation
        assert tokens[5].is_sent_start
        assert tokens[10].is_sent_start

    def test_french_tokenization_1(self):
        text = (
            """a dénoncé la montée en puissance d'un « complexe techno-industriel »"""
        )
        tokens = tokenize_text_flat_array(text, self.fr_lang, False)
        assert [
            "a",
            "dénoncé",
            "la",
            "montée",
            "en",
            "puissance",
            "d'un",
            "«",
            "complexe",
            "techno-industriel",
            "»",
        ] == [t.text for t in tokens]

    def test_spanish_tokenization_1(self):
        text = """¿qué es esto?"""
        tokens = tokenize_text_flat_array(text, self.es_lang, False)
        assert ["¿", "qué", "es", "esto", "?"] == [t.text for t in tokens]

    def test_german_tokenization_1(self):
        text = """Zeit der von Lynch zusammen mit Mark Frost geschaffenen Serie „Twin Peaks“"""
        tokens = tokenize_text_flat_array(text, self.de_lang, False)
        assert [
            "Zeit",
            "der",
            "von",
            "Lynch",
            "zusammen",
            "mit",
            "Mark",
            "Frost",
            "geschaffenen",
            "Serie",
            "„",
            "Twin",
            "Peaks",
            "“",
        ] == [t.text for t in tokens]
        # assert tokens[10].is_left_punct
        # assert tokens[12].is_right_punct

    def test_danish_tokenization_1(self):
        text = """»Vi kan gøre det,« siger Mikkel."""
        tokens = tokenize_text_flat_array(text, self.da_lang, False)
        assert ["»", "Vi", "kan", "gøre", "det", ",", "«", "siger", "Mikkel", "."] == [
            t.text for t in tokens
        ]
        # Question? should it be like this?
        # assert tokens[0].is_left_punct
        # assert tokens[6].is_right_punct

    def test_danish_tokenization_2(self):
        text = (
            """I 2028 skal den evalueres på Danske Filmkritikeres generalforsamling."""
        )
        tokens = tokenize_text_flat_array(text, self.da_lang, False)
        assert [
            "I",
            "2028",
            "skal",
            "den",
            "evalueres",
            "på",
            "Danske",
            "Filmkritikeres",
            "generalforsamling",
            ".",
        ] == [t.text for t in tokens]
        assert tokens[1].is_like_num

    def test_url_detection(self):
        # Generated URLs from https://www.randomlists.com/urls?qty=50

        urls = TokenizationTest._load_example_file("random_urls.txt")
        tokens = [tokenize_text_flat_array(u, self.en_lang, False)[0] for u in urls]
        for i in range(len(urls)):
            assert tokens[i].text == urls[i]
            assert tokens[i].is_like_url

    def test_email_detection(self):
        # Generated URLs from https://www.randomlists.com/urls?qty=50

        emails = TokenizationTest._load_example_file("random_emails.txt")
        tokens = [tokenize_text_flat_array(e, self.en_lang, False)[0] for e in emails]
        for i in range(len(tokens)):
            assert tokens[i].text == emails[i]
            assert tokens[i].is_like_email

    def test_number_detection(self):
        # Generated URLs from https://www.randomlists.com/urls?qty=50

        numbers = TokenizationTest._generate_random_numbers()
        tokens = [
            tokenize_text_flat_array(str(n), self.en_lang, False)[0] for n in numbers
        ]
        for i in range(len(tokens)):
            assert tokens[i].text == numbers[i]
            assert tokens[i].is_like_num
