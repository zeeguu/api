import flask
from flask import request

from . import api
from .utils.json_result import json_result
from .utils.route_wrappers import cross_domain, with_session
from zeeguu.language.text_difficulty import text_difficulty
from zeeguu.language.text_learnability import text_learnability
from zeeguu.model import SethiKnowledgeEstimator, KnownWordProbability, Language


@api.route("/get_difficulty_for_text/<lang_code>", methods=("POST",))
@cross_domain
@with_session
def get_difficulty_for_text(lang_code):
    """
    URL parameters:
    :param lang_code: the language of the text

    Json data:
    :param texts: json array that contains the texts to calculate the difficulty for. Each text consists of an array
        with the text itself as 'content' and an additional 'id' which gets roundtripped unchanged
    :param difficulty_computer (optional): calculate difficulty score using a specific algorithm
    :param rank_boundary (deprecated): upper boundary for word frequency rank (between 1 and 10'000)
    :param personalized (deprecated): by default we always compute the personalized difficulty

    For an example of how the Json data looks like, see
        ../tests/api_tests.py#test_txt_difficulty(self):

    :return difficulties: json array, which contains for each text:
      * estimated_difficulty - one of three: "EASY", "MEDIUM", "HARD"
      * id - identifies the text
      * [deprecated] score_average - average difficulty of the words in the text
      * [deprecated] score_median - median difficulty of the words in the text
    """
    language = Language.find(lang_code)
    if not language:
        return 'FAIL'

    data = request.get_json()

    if not 'texts' in data:
        return 'FAIL'

    texts = []
    for text in data['texts']:
        texts.append(text)

    difficulty_computer = 'default'
    if 'difficulty_computer' in data:
        difficulty_computer = data['difficulty_computer'].lower()

    user = flask.g.user
    known_probabilities = KnownWordProbability.find_all_by_user_cached(user)

    difficulties = []
    for text in texts:
        difficulty = text_difficulty(
                text["content"],
                language,
                known_probabilities,
                difficulty_computer
                )
        difficulty["id"] = text["id"]
        difficulties.append(difficulty)

    return json_result(dict(difficulties=difficulties))


@api.route("/get_learnability_for_text/<lang_code>", methods=("POST",))
@cross_domain
@with_session
def get_learnability_for_text(lang_code):
    """
    URL parameters:
    :param lang_code: the language of the text

    Json data:
    :param texts: json array that contains the texts to calculate the learnability for. Each text consists of an array
        with the text itself as 'content' and an additional 'id' which gets roundtripped unchanged
        For an example of how the Json data looks like, see
            ../tests/api_tests.py#test_text_learnability(self):


    :return learnabilities: json array, contains the learnabilities as arrays with the key 'score' for the learnability
        value (percentage of words from the text that the user is currently learning), the 'count' of the learned
        words in the text and the 'id' parameter to identify the corresponding text
    """
    user = flask.g.user

    language = Language.find(lang_code)
    if language is None:
        return 'FAIL'

    data = request.get_json()

    texts = []
    if 'texts' in data:
        for text in data['texts']:
            texts.append(text)
    else:
        return 'FAIL'

    learnabilities = []
    for text in texts:
        e = SethiKnowledgeEstimator(user)
        count, learnability = text_learnability(text, e.words_being_learned(language))
        learnabilities.append(dict(score=learnability, count=count, id=text['id']))

    return json_result(dict(learnabilities=learnabilities))
