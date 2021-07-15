import string

from zeeguu.core import model
from zeeguu.core.language.difficulty_estimator_strategy import DifficultyEstimatorStrategy
import nltk
import math
import re
from wordstats import Word
from textblob import TextBlob


class WordRankDifficultyEstimator(DifficultyEstimatorStrategy):
    """
    Difficulty estimator based on word-rank and sentence length
    difficulty equation inspired by flesch-kincaid
    """

    CUSTOM_NAMES = ["wr", "wrscore", "word-rank-score"]

    #todo remove names from text
    @classmethod
    def estimate_difficulty(cls, text: str, language: 'model.Language', user: 'model.User'):
        '''
        Estimates the difficulty based on the word-rank.
        :param text: See DifficultyEstimatorStrategy
        :param language: See DifficultyEstimatorStrategy
        :param user: See DifficultyEstimatorStrategy
        :rtype: dict
        :return: The dictionary contains the keys and return types
                    normalized: float (0<=normalized<=1)
                    discrete: string [EASY, MEDIUM, HARD]
        '''
        word_rank_score = cls.word_rank_readability_score(text, language)

        difficulty_scores = dict(
            normalized=cls.normalize_difficulty(word_rank_score),
            discrete=cls.discrete_difficulty(word_rank_score)
        )

        return word_rank_score

    @classmethod
    def word_rank_readability_score(cls, text: str, language: 'model.Language'):

        langtb = TextBlob(text).detect_language()
        words = nltk.word_tokenize(text)

        #detect and remove proper nouns
        if 1 == 0:
            words = []
            sentences = nltk.sent_tokenize(text)
            for s in sentences:
                # print(s)
                tokens = nltk.word_tokenize(s)
                words.append(tokens[0])
                for i in range(1, len(tokens)):
                    if not str.isupper(tokens[i][0]):
                        words.append(tokens[i])

        #remove punctuation
        words = [w for w in words if w not in string.punctuation]
        #remove digits (or dates)
        words = [w for w in words if re.search("\d", w) == None]

        #translate tokens
        words_trans = words.copy()
        for i in range(len(words)):
            try:
                translation = TextBlob(words[i]).translate(from_lang=langtb, to='en')
                words_trans[i] = translation
                print("translated: ", words[i], "to: ", words_trans[i])
            except:
                print("not translated: ", words[i])


        #remove equivalent words, assume they are cognates and therefore not difficult
        words = [words[i] for i in range(len(words)) if words_trans[i].lower != words[i].lower()]


        number_of_words = len(words)

        number_of_sentences = len(nltk.sent_tokenize(text))

        constants = cls.get_constants_for_language(language);

        #calculate word rank per word
        words_stat = [Word.stats(w, language.code) for w in words]
        #throw away words that do not occur in the top 50k
        difficulties = [w.difficulty for w in words_stat if w.frequency is not 0]
        number_of_words = len(difficulties)

        #index = constants["start"] - constants["sentence"] * (number_of_words / number_of_sentences) \
        #        - constants["word"] * (sum(difficulties) / number_of_words)
        #average difficulty of text
        return sum(difficulties) / number_of_words

    @classmethod
    def get_constants_for_language(cls, language: 'model.language'):
        #if language.code == "de":
        #    return {"start": 180, "sentence": 1, "word": 58.5}
        #else:
        return {"start": 130.835, "sentence": 1.015, "word": 180.6}

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
