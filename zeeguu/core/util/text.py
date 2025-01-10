import math

import nltk
import pyphen
import regex
from collections import Counter
from nltk import SnowballStemmer
from zeeguu.core.model.language import Language
from logging import log
from string import punctuation
import re


AVERAGE_SYLLABLE_LENGTH = 2.5

"""
    Collection of simple text processing functions
"""


class Token:
    PUNCTUATION = "»«" + punctuation
    LEFT_PUNCTUATION = "<«({#"
    RIGHT_PUNCTUATION = ">»)}"
    NUM_REGEX = re.compile(r"[0-9]+(\.|,)*[0-9]*")

    def __init__(self, text, par_i=None, sent_i=None, token_i=None):
        """
        sent_i - the sentence in the overall text.
        token_i - the index of the token in the original sentence.
        """
        self.text = text
        self.is_sent_start = token_i == 0
        self.is_punct = text in Token.PUNCTUATION
        self.is_left_punct = text in Token.LEFT_PUNCTUATION
        self.is_right_punct = text in Token.RIGHT_PUNCTUATION
        self.is_like_num = Token.NUM_REGEX.match(text) is not None
        self.par_i = par_i
        self.sent_i = sent_i
        self.token_i = token_i

    def __repr__(self):
        return self.text

    def as_serializable_dictionary(self):
        return {
            "text": self.text,
            "is_sent_start": self.is_sent_start,
            "is_punct": self.is_punct,
            "is_left_punct": self.is_left_punct,
            "is_right_punct": self.is_right_punct,
            "is_like_num": self.is_like_num,
            "sent_i": self.sent_i,
            "token_i": self.token_i,
            "paragraph_i": self.par_i,
        }


def split_into_paragraphs(text):
    paragraph_delimiter = re.compile(r"\n\n")
    return paragraph_delimiter.split(text)


def split_words_from_text(text):
    words = regex.findall(r"(\b\p{L}+\b)", text)
    return words


def tokenize_text(text: str, language: Language, as_serializable_dictionary=True):
    try:
        tokens = [
            [
                [
                    (
                        Token(w, par_i, sent_i, w_i).as_serializable_dictionary()
                        if as_serializable_dictionary
                        else Token(w, par_i, sent_i, w_i)
                    )
                    for w_i, w in enumerate(
                        nltk.word_tokenize(sent, language=language.name.lower())
                    )
                ]
                for sent_i, sent in enumerate(
                    sent_tokenizer_text(paragraph, language=language)
                )
            ]
            for par_i, paragraph in enumerate(split_into_paragraphs(text))
        ]
        return tokens
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        log(
            2,
            f"Failed 'word_tokenize' for language: '{language.name.lower()}', defaulted to 'english'",
        )
        log(2, e)
        tokens = [
            [
                [
                    (
                        Token(w, par_i, sent_i, w_i).as_serializable_dictionary()
                        if as_serializable_dictionary
                        else Token(w, par_i, sent_i, w_i)
                    )
                    for w_i, w in enumerate(nltk.word_tokenize(sent))
                ]
                for sent_i, sent in enumerate(sent_tokenizer_text(paragraph))
            ]
            for par_i, paragraph in enumerate(split_into_paragraphs(text))
        ]
        return tokens


def sent_tokenizer_text(text: str, language: Language):
    try:
        return nltk.tokenize.sent_tokenize(text, language=language.name.lower())
    except Exception as e:
        from sentry_sdk import capture_exception

        capture_exception(e)
        log(
            2,
            f"Failed 'sent_tokenize' for language: '{language.name.lower()}', defaulted to 'english'",
        )
        log(2, e)
        return nltk.tokenize.sent_tokenize(text)


def number_of_sentences(text):
    return len(nltk.sent_tokenize(text))


def split_unique_words_from_text(text, language: Language):
    words = split_words_from_text(text)
    stemmer = SnowballStemmer(language.name.lower())
    return set([stemmer.stem(w.lower()) for w in words])


def length(text):
    return len(split_words_from_text(text))


def unique_length(text, language: Language):
    words_unique = split_unique_words_from_text(text, language)
    return len(words_unique)


def average_sentence_length(text):
    return length(text) / number_of_sentences(text)


def median_sentence_length(text):
    sentence_lengths = [length(s) for s in nltk.sent_tokenize(text)]
    sentence_lengths = sorted(sentence_lengths)

    return sentence_lengths[int(len(sentence_lengths) / 2)]


def number_of_syllables(text, language: Language):
    words = [w.lower() for w in split_words_from_text(text)]

    number_of_syllables = 0
    for word, freq in Counter(words).items():
        if language.code == "zh-CN":
            syllables = int(math.floor(max(len(word) / AVERAGE_SYLLABLE_LENGTH, 1)))
        else:
            dic = pyphen.Pyphen(lang=language.code)
            syllables = len(dic.positions(word)) + 1

        number_of_syllables += syllables * freq

    return number_of_syllables


def average_word_length(text, language: Language):
    return number_of_syllables(text, language) / length(text)


def median_word_length(text, language: Language):
    word_lengths = [
        number_of_syllables(w, language) for w in split_words_from_text(text)
    ]
    return word_lengths[int(len(word_lengths) / 2)]
