import nltk
import pyphen
from numpy import math

from zeeguu.core.language.difficulty_estimator_strategy import (
    DifficultyEstimatorStrategy,
)
from zeeguu.core.util.text import split_words_from_text
from zeeguu.core.model.language import Language
from collections import Counter


class FleschKincaidDifficultyEstimator(DifficultyEstimatorStrategy):
    """
    The Flesch-Kincaid readability index is a classic readability index.
    Wikipedia : https://en.wikipedia.org/wiki/Flesch–Kincaid_readability_tests
    """

    AVERAGE_SYLLABLE_LENGTH = 2.5  # Simplifies the syllable counting
    CUSTOM_NAMES = ["fk", "fkindex", "flesch-kincaid"]

    @classmethod
    def estimate_difficulty(cls, text: str, language: "Language", user: "User"):
        """
        Estimates the difficulty based on the Flesch-Kincaid readability index.
        :param text: See DifficultyEstimatorStrategy
        :param language: See DifficultyEstimatorStrategy
        :param user: See DifficultyEstimatorStrategy
        :rtype: dict
        :return: The dictionary contains the keys and return types
                    normalized: float (0<=normalized<=1)
                    discrete: string [EASY, MEDIUM, HARD]
        """
        flesch_kincaid_index = cls.flesch_kincaid_readability_index(text, language)

        difficulty_scores = dict(
            normalized=cls.normalize_difficulty(flesch_kincaid_index),
            discrete=cls.discrete_difficulty(flesch_kincaid_index),
            grade=cls.grade_difficulty(flesch_kincaid_index),
            cefr_level=cls.discrete_difficulty_CEFR(flesch_kincaid_index),
        )

        return difficulty_scores

    @classmethod
    def flesch_kincaid_readability_index(cls, text: str, language: "Language"):
        words = [w.lower() for w in split_words_from_text(text)]

        number_of_syllables = 0
        number_of_words = len(words)
        for word, freq in Counter(words).items():
            syllables_in_word = cls.estimate_number_of_syllables_in_word_pyphen(
                word, language
            )
            number_of_syllables += syllables_in_word * freq

        number_of_sentences = len(nltk.sent_tokenize(text))

        constants = cls.get_constants_for_language(language)

        try:
            index = (
                constants["start"]
                - constants["sentence"] * (number_of_words / number_of_sentences)
                - constants["word"] * (number_of_syllables / number_of_words)
            )
        except ZeroDivisionError:
            index = 0

        return index

    @classmethod
    def get_constants_for_language(cls, language: "language"):
        # Constants & references https://github.com/Yoast/YoastSEO.js/issues/267#issue-132433796
        # INFO: es/it/nl use ( syllables / 100 words ) instead of ( total syllables / total words )
        # Multiplying the constants by 100 should approximate this
        if language.code in ["es", "pt"]:
            return {"start": 206.84, "sentence": 1.02, "word": 60}
        if language.code == "it":
            return {"start": 217, "sentence": 1.3, "word": 60}
        if language.code == "nl":
            return {"start": 206.84, "sentence": 0.93, "word": 77}
        if language.code == "fr":
            return {"start": 207, "sentence": 1.015, "word": 73.6}
        if language.code in ["ru", "pl"]:
            return {"start": 206.835, "sentence": 1.3, "word": 60.1}
        if language.code in ["de", "da"]:
            return {"start": 180, "sentence": 1, "word": 58.5}
        return {"start": 206.835, "sentence": 1.015, "word": 84.6}

    @classmethod
    def estimate_number_of_syllables_in_word(cls, word: str, language: "Language"):
        if len(word) < cls.AVERAGE_SYLLABLE_LENGTH:
            syllables = 1  # Always at least 1 syllable
        else:
            syllables = len(word) / cls.AVERAGE_SYLLABLE_LENGTH
        return int(math.floor(syllables))  # Truncate the number of syllables

    @classmethod
    def estimate_number_of_syllables_in_word_pyphen(
        cls, word: str, language: "Language"
    ):

        if language.code == "zh-CN":
            if len(word) < cls.AVERAGE_SYLLABLE_LENGTH:
                syllables = 1  # Always at least 1 syllable
            else:
                syllables = len(word) / cls.AVERAGE_SYLLABLE_LENGTH
            return int(math.floor(syllables))  # Truncate the number of syllables
        else:
            # pyphen can't hyphenate on 'no' - so we use 'nb' instead
            code = "nb" if language.code == "no" else language.code
            dic = pyphen.Pyphen(lang=code)
            syllables = len(dic.positions(word)) + 1
            return syllables

    @classmethod
    def normalize_difficulty(cls, score: int):
        if score < 0:
            return 1
        elif score > 100:
            return 0
        else:
            return round(1 - (score * 0.01), 2)

    @classmethod
    def discrete_difficulty(cls, score: int):
        if score > 80:
            return "EASY"
        elif score > 50:
            return "MEDIUM"
        else:
            return "HARD"

    @classmethod
    def discrete_difficulty_CEFR(cls, score: int):
        # Divided the scale into 6 bands
        if score > 83:
            return "A1"
        elif score > 66:
            return "A2"
        elif score > 49:
            return "B1"
        elif score > 32:
            return "B2"
        elif score > 15:
            return "C1"
        else:
            return "C2"

    @classmethod
    def grade_difficulty(cls, score: int):
        if score < 0:
            return 100
        elif score > 100:
            return 0
        else:
            return int(round(100 - score))
