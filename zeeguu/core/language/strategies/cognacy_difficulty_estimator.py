from numpy import mean
from wordstats import Word, WordInfo
from zeeguu.core import model
from zeeguu.core.language.difficulty_estimator_strategy import DifficultyEstimatorStrategy
from zeeguu.core.util.text import split_words_from_text
from zeeguu.core.model import UserWord, Language
from nltk.stem import SnowballStemmer
from wordstats.cognate_evaluation import CognateEvaluation
from wordstats.edit_distance import EditDistance
from collections import defaultdict, Counter

from zeeguu.core.constants import WIH_READ_CLICKED, WIH_READ_NOT_CLICKED_IN_SENTENCE, WIH_READ_NOT_CLICKED_OUT_SENTENCE

class CognacyDifficultyEstimator(DifficultyEstimatorStrategy):

    CUSTOM_NAMES = ["cognacy"]

    def __init__(self, language: 'model.Language', user: 'model.User'):
        self.user = user
        self.language = language
        self.score_map = dict()

    # creates estimator that determines the ratio of new words for a given text
    @classmethod
    def cognacyRatio(cls, language: 'model.Language', user: 'model.User'):
        """
                This estimator computes the ratio of new words for a given user and language
                :param language: language of the text that needs to be estimated
                :param user: the user for which the difficulty estimation needs to be done
                :rtype: WordHistoryDifficultyEstimator
                :return: WordHistoryDifficultyEstimator with initialized user, language and word => score map
                        which can be used for determining scores for multiple articles for the same user and language
        """

        estimator = cls(language, user)

        # fetch cognates
        cognate_info = CognateEvaluation.load_cached(language.code, user.native_language.code, EditDistance)

        # stem cognates, assign difficulty of 0
        cognates = cognate_info.whitelist.keys()
        stemmer = SnowballStemmer(language.name.lower())

        cognates = list(set([stemmer.stem(c.lower()) for c in cognates]))
        words_score = [0 for e in cognates]

        estimator.score_map = dict(zip(cognates, words_score))

        return estimator

    def estimate_difficulty(self, text: str):
        """
        This estimator computes the difficulty based on the scoring map
        :param text: See DifficultyEstimatorStrategy
        :rtype: dict
        :return: The dictionary contains the keys and return types
                    normalized: float (0<=normalized<=1)
                    discrete: string [EASY, MEDIUM, HARD]
        """

        # split and stem words
        words = split_words_from_text(text)
        stemmer = SnowballStemmer(self.language.name.lower())
        words = [stemmer.stem(w.lower()) for w in words]

        # frequency and length
        word_frequency = Counter(words)
        total_words = len(words)

        # score per word
        word_scores = {w: self.word_difficulty(self.score_map, True, w) for w in word_frequency}

        if (len(word_scores)) == 0:

            difficulty_scores = dict(
                median=1.0,
                median_unique=1.0,
                normalized=1.0,
                discrete= "HARD",
                unique_ratio=1.0
            )
        else:

            # words above median score
            word_scores_sorted= sorted(word_scores.items(), key=lambda item: item[1])
            center = int(round(len(word_scores_sorted) / 2, 0))
            word_scores_median = dict(word_scores_sorted[center:])
            total_words_median = sum([word_frequency[w] for w in word_scores_median])

            difficulty_scores = dict(
                median=sum([ s*word_frequency[w] for w, s in word_scores_median.items()])/total_words_median,
                median_unique=mean(list(word_scores_median.values())),
                normalized=sum([ s*word_frequency[w] for w, s in word_scores.items()])/total_words,             # Originally called 'score_average'
                #todo: discrete=discrete_difficulty,               # Originally called 'estimated_difficulty'
                unique_ratio=mean(list(word_scores.values()))      # Ratio of non-cognates
            )

        return difficulty_scores

    @classmethod
    def discrete_text_difficulty(cls, median_difficulty: float):
        """
        :param median_difficulty:
        :return: a symbolic representation of the estimated difficulty
         the values are between "EASY", "MEDIUM", and "HARD"
        """
        if median_difficulty < 0.3:
            return "EASY"
        if median_difficulty < 0.4:
            return "MEDIUM"
        return "HARD"

    @classmethod
    # TODO: must test this thing
    def word_difficulty(cls, known_probabilities: dict, personalized: bool, word: Word):
        """
        # estimate the difficulty of a word, given:
            :param word_info:
            :param known_probabilities:
            :param personalized:
            :param word:

        :return: a normalized value where 0 is (easy) and 1 is (hard)
        """

        # Assume word is difficult and unknown
        estimated_difficulty = 1.0

        # Check if the user knows the word
        try:
            known_probability = known_probabilities[word]  # Value between 0 (unknown) and 1 (known)
        except KeyError:
            known_probability = None

        if personalized and known_probability is not None:
            estimated_difficulty = float(known_probability)

        return estimated_difficulty

