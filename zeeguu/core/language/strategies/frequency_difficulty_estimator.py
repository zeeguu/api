from nltk import SnowballStemmer
from wordstats import Word, WordInfo
from zeeguu.core import model
from zeeguu.core.language.difficulty_estimator_strategy import DifficultyEstimatorStrategy
from zeeguu.core.util.text import split_words_from_text
from wordstats.file_handling.loading_from_hermit import *
from collections import defaultdict

class FrequencyDifficultyEstimator(DifficultyEstimatorStrategy):

    CUSTOM_NAMES = ["frequency"]

    def __init__(self, language: 'model.Language'):
        self.language = language
        self.score_map = dict()

        # determines word scores
        #words_history = WordInteractionHistory.find_all_word_histories_for_user_language(user, language)

        #words_found = [w.word.word.lower() for w in words_history]
        #event_history = [w.interaction_history for w in words_history]

        #words_score = [max(1 - len(e) / 1, 0) for e in event_history]

    @classmethod
    def quadratic(cls, language: 'model.Language'):
        """
                This estimator computes the ratio of new words for a given user and language
                :param language: language of the text that needs to be estimated
                :param user: the user for which the difficulty estimation needs to be done
                :rtype: WordHistoryDifficultyEstimator
                :return: WordHistoryDifficultyEstimator with initialized user, language and word => score map
                        which can be used for determining scores for multiple articles for the same user and language
        """

        estimator = cls(language)

        freq_list = load_language_from_hermit(language.code)

        word_dict = dict()
        for k,v in freq_list.word_info_dict.items():
            word_dict[k] = v.frequency

        stemmer = SnowballStemmer(language.name.lower())

        score_map = defaultdict(int)

        for k, v in word_dict.items():
            score_map[stemmer.stem(k.lower())] += v

        max_freq = max(score_map.values())

        for k in score_map.keys():
            score_map[k] = (1 - score_map[k] / max_freq)**0.5

        estimator.score_map = score_map

        return estimator

    def estimate_difficulty(self, text: str):
        """
        This estimator computes the difficulty based on how often words in the text are used in the given language
        :param text: See DifficultyEstimatorStrategy
        :param language: See DifficultyEstimatorStrategy
        :param user: See DifficultyEstimatorStrategy
        :rtype: dict
        :return: The dictionary contains the keys and return types
                    normalized: float (0<=normalized<=1)
                    discrete: string [EASY, MEDIUM, HARD]
        """
        # Calculate difficulty for each word
        words = split_words_from_text(text)

        stemmer = SnowballStemmer(self.language.name.lower())
        words = [stemmer.stem(w.lower()) for w in words]

        words_freq = defaultdict(int)
        total_words = 0
        for w in words:
            total_words += 1
            words_freq[w] += 1

        word_scores = [self.word_difficulty(self.score_map, True, w) * (words_freq[w] / total_words) for w in
                       words_freq.keys()]

        # If we can't compute the text difficulty, we estimate hard
        if (len(word_scores)) == 0:
            normalized_estimate = 1.00
            words_new = 1.00
            discrete_difficulty = "HARD"
        else:
            # Median difficulty is used for discretization
            word_scores.sort()
            center = int(round(len(word_scores) / 2, 0))
            difficulty_median = word_scores[center]

            normalized_estimate = sum(word_scores)
            discrete_difficulty = self.discrete_text_difficulty(difficulty_median)

        difficulty_scores = dict(
            normalized=normalized_estimate,  # Originally called 'score_average'
            discrete=discrete_difficulty  # Originally called 'estimated_difficulty'
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
    def word_difficulty(cls, known_probabilities: dict, personalized: bool, w):
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
            known_probability = known_probabilities[w]  # Value between 0 (unknown) and 1 (known)
        except KeyError:
            known_probability = None

        if personalized and known_probability is not None:
            estimated_difficulty = float(known_probability)

        return estimated_difficulty

