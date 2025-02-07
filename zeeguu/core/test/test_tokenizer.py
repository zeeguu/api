from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.tokenization import get_tokenizer, TokenizerModel
from zeeguu.core.test.rules.language_rule import LanguageRule
import os
import random

"""
    These tests are done for the Stanza tokenizer, as this is the model we are expecting
    to use in production.
"""


class TokenizationTest(ModelTestMixIn):
    def setUp(self):
        super().setUp()
        self.en_lang = LanguageRule.get_or_create_language("en")
        self.es_lang = LanguageRule.get_or_create_language("es")
        self.de_lang = LanguageRule.get_or_create_language("de")
        self.fr_lang = LanguageRule.get_or_create_language("fr")
        self.da_lang = LanguageRule.get_or_create_language("da")
        self.it_lang = LanguageRule.get_or_create_language("it")
        self.pt_lang = LanguageRule.get_or_create_language("pt")
        self.tokenizer_model = TokenizerModel.STANZA_TOKEN_ONLY
        self.en_tokenizer = get_tokenizer(self.en_lang, self.tokenizer_model)
        self.es_tokenizer = get_tokenizer(self.es_lang, self.tokenizer_model)
        self.de_tokenizer = get_tokenizer(self.de_lang, self.tokenizer_model)
        self.fr_tokenizer = get_tokenizer(self.fr_lang, self.tokenizer_model)
        self.da_tokenizer = get_tokenizer(self.da_lang, self.tokenizer_model)
        self.it_tokenizer = get_tokenizer(self.it_lang, self.tokenizer_model)
        self.pt_tokenizer = get_tokenizer(self.pt_lang, self.tokenizer_model)

    @classmethod
    def assert_sentence_i_token_i_is_correct(cls, token_list, sent_i=0):
        """
        Used to check if the tokens all belog to the same sentence and have the
        right coordinates.
        """
        assert all(
            [t.sent_i == sent_i and t.token_i == i for i, t in enumerate(token_list)]
        )

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
        text = "This is a test sentence."
        tokens = self.en_tokenizer.tokenize_text(text, False)
        assert ["This", "is", "a", "test", "sentence", "."] == [t.text for t in tokens]
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens)
        assert tokens[-1].is_punctuation
        assert tokens[0].is_sent_start

    def test_english_sentence_2(self):
        text = "I have (parentheses) in this sentence."
        tokens = tokens = self.en_tokenizer.tokenize_text(text, False)
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
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens)
        assert tokens[0].is_sent_start
        assert tokens[-1].is_punctuation

    def test_english_sentence_3(self):
        text = "It's a sentence. Sentence two is here. Sentence three is the last one."
        tokens = self.en_tokenizer.tokenize_text(text, False)
        assert [
            "It's",
            "a",
            "sentence",
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
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens[:4])
        assert tokens[4].is_sent_start
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens[4:9], 1)
        assert tokens[9].is_sent_start
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens[9:], 2)

    def test_english_sentence_4(self):
        text = "Paragraph 1.\n\nParagraph 2.\n\nLong text here in paragraph 3."
        tokens = self.en_tokenizer.tokenize_text(text, False)
        assert [
            "Paragraph",
            "1",
            ".",
            "Paragraph",
            "2",
            ".",
            "Long",
            "text",
            "here",
            "in",
            "paragraph",
            "3",
            ".",
        ] == [t.text for t in tokens]
        assert tokens[0].par_i == 0
        assert tokens[3].par_i == 1
        assert tokens[6].par_i == 2

    def test_english_sentence_4(self):
        """
        Tests a case where the accumulator wouldn't have anything to accumulate
        and if not checking for this condition it wouldn't return any tokens.
        """
        text = "Year’"
        tokens = self.en_tokenizer.tokenize_text(text, False)
        assert ["Year", "’"] == [t.text for t in tokens]

    def test_french_tokenization_1(self):
        text = (
            """a dénoncé la montée en puissance d'un « complexe techno-industriel »"""
        )
        tokens = self.fr_tokenizer.tokenize_text(text, False)
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
        assert all([t.token_i == i for i, t in enumerate(tokens)])

    def test_spanish_tokenization_1(self):
        text = """¿qué es esto?"""
        tokens = self.es_tokenizer.tokenize_text(text, False)
        assert ["¿", "qué", "es", "esto", "?"] == [t.text for t in tokens]
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens)

    def test_spanish_tokenization_2(self):
        text = """La alternativa a este modelo es la «hipótesis monogenista», conocida popularmente como «Eva africana»"""
        tokens = self.es_tokenizer.tokenize_text(text, False)
        assert [
            "La",
            "alternativa",
            "a",
            "este",
            "modelo",
            "es",
            "la",
            "«",
            "hipótesis",
            "monogenista",
            "»",
            ",",
            "conocida",
            "popularmente",
            "como",
            "«",
            "Eva",
            "africana",
            "»",
        ] == [t.text for t in tokens]
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens)

    def test_german_tokenization_1(self):
        text = """Zeit der von Lynch zusammen mit Mark Frost geschaffenen Serie „Twin Peaks“"""
        tokens = self.de_tokenizer.tokenize_text(text, False)
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
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens)
        # assert tokens[10].is_left_punct
        # assert tokens[12].is_right_punct

    def test_italian_tokenization_1(self):
        text = """La scelta di affidare l’interpretazione del cantautore all’idolo della..."""
        tokens = self.it_tokenizer.tokenize_text(text, False)
        assert [
            "La",
            "scelta",
            "di",
            "affidare",
            "l’interpretazione",
            "del",
            "cantautore",
            "all’idolo",
            "della",
            "...",
        ] == [t.text for t in tokens]
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens)

    def test_danish_tokenization_1(self):
        text = """»Vi kan gøre det,« siger Mikkel."""
        tokens = self.da_tokenizer.tokenize_text(text, False)
        assert ["»", "Vi", "kan", "gøre", "det", ",", "«", "siger", "Mikkel", "."] == [
            t.text for t in tokens
        ]
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens)
        # Question? should it be like this?
        # assert tokens[0].is_left_punct
        # assert tokens[6].is_right_punct

    def test_danish_tokenization_2(self):
        text = (
            """I 2028 skal den evalueres på Danske Filmkritikeres generalforsamling."""
        )
        tokens = self.da_tokenizer.tokenize_text(text, False)
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
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens)

    def test_portuguese_tokenization_1(self):
        text = """Eu estou a testar o Tokenizer nas frazes do Zeeguu."""
        tokens = self.pt_tokenizer.tokenize_text(text, False)
        assert [
            "Eu",
            "estou",
            "a",
            "testar",
            "o",
            "Tokenizer",
            "nas",
            "frazes",
            "do",
            "Zeeguu",
            ".",
        ] == [t.text for t in tokens]
        assert tokens[0].is_sent_start
        TokenizationTest.assert_sentence_i_token_i_is_correct(tokens)

    def test_url_detection(self):
        # Generated URLs from https://www.randomlists.com/urls?qty=50

        urls = TokenizationTest._load_example_file("random_urls.txt")
        tokens = [self.en_tokenizer.tokenize_text(u, False)[0] for u in urls]
        urls_parsed = 0
        urls_failed_tokens = []
        for i in range(len(urls)):
            if tokens[i].text == urls[i] and tokens[i].is_like_url:
                urls_parsed += 1
            else:
                urls_failed_tokens.append(tokens[i].text)
        assert (
            [] == urls_failed_tokens
        ), f"Parsed a total of {urls_parsed}/{len(urls)}, {" ".join(urls_failed_tokens)}"
        # Some cases which gave issues:
        assert not self.en_tokenizer.tokenize_text("e.v.t..", False)[0].is_like_url

    def test_email_detection(self):
        # Generated URLs from https://www.randomlists.com/urls?qty=50

        emails = TokenizationTest._load_example_file("random_emails.txt")
        tokens = [self.en_tokenizer.tokenize_text(e, False)[0] for e in emails]
        for i in range(len(tokens)):
            assert tokens[i].text == emails[i]
            assert tokens[i].is_like_email

    def test_number_detection(self):
        # Generated URLs from https://www.randomlists.com/urls?qty=50

        numbers = TokenizationTest._generate_random_numbers()
        tokens = [self.en_tokenizer.tokenize_text(n, False)[0] for n in numbers]
        for i in range(len(tokens)):
            assert tokens[i].text == numbers[i]
            assert tokens[i].is_like_num
