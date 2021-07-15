import math

import nltk
import pyphen
import regex
from collections import Counter
from nltk import SnowballStemmer
from zeeguu.core.model import Language

AVERAGE_SYLLABLE_LENGTH = 2.5

"""
    Collection of simple text processing functions
"""


def split_words_from_text(text):
    words = regex.findall(r'(\b\p{L}+\b)', text)
    return words

def split_unique_words_from_text(text, language:Language):
    words = split_words_from_text(text)
    stemmer = SnowballStemmer(language.name.lower())
    return set([stemmer.stem(w.lower()) for w in words])

def length(text):
    return len(split_words_from_text(text))

def unique_length(text, language: Language):
    words_unique = split_unique_words_from_text(text, language)
    return len(words_unique)

def number_of_sentences(text):
    return len(nltk.sent_tokenize(text))

def average_sentence_length(text):
    return length(text)/number_of_sentences(text)

def median_sentence_length(text):
    sentence_lengths = [length(s) for s in nltk.sent_tokenize(text)]
    sentence_lengths = sorted(sentence_lengths)

    return sentence_lengths[int(len(sentence_lengths)/2)]

def number_of_syllables(text, language:Language):
    words = [w.lower() for w in split_words_from_text(text)]

    number_of_syllables = 0
    for word, freq in Counter(words).items():
        if language.code == "zh-CN":
            syllables = int(math.floor(max(len(word) / AVERAGE_SYLLABLE_LENGTH,1)))
        else:
            dic = pyphen.Pyphen(lang=language.code)
            syllables = len(dic.positions(word)) + 1

        number_of_syllables += syllables * freq

    return number_of_syllables

def average_word_length(text, language:Language):
    return number_of_syllables(text, language)/length(text)

def median_word_length(text, language:Language):
    word_lengths = [number_of_syllables(w, language) for w in split_words_from_text(text)]
    return word_lengths[int(len(word_lengths)/2)]



