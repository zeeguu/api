import flask
from flask import request
from zeeguu.content_retriever.parallel_retriever import get_content_for_urls
from zeeguu.model import Language

from utils.route_wrappers import cross_domain, with_session
from utils.json_result import json_result

from . import api


# TODO: One day i'll deprecate this...
@api.route("/get_content_from_url", methods=("POST",))
@cross_domain
@with_session
def get_content_from_url():
    """
    Json data:
    :param urls: json array that contains the urls to get the article content for. Each url consists of an array
        with the url itself as 'url' and an additional 'id' which gets roundtripped unchanged.
        For an example of how the Json data looks like, see
            ../tests/api_tests.py#test_content_from_url(self):

    :param timeout (optional): maximal time in seconds to wait for the results

    :param lang_code (optional): If the user sends along the language, then we compute the difficulty of the texts

    :return contents: json array, contains the contents of the urls that responded within the timeout as arrays
        with the key 'content' for the article content, the url of the main image as 'image' and the 'id' parameter
        to identify the corresponding url

    """
    data = request.get_json()

    urls = []
    if 'urls' in data:
        for url in data['urls']:
            urls.append(url['url'])
    else:
        return 'FAIL'

    if 'timeout' in data:
        timeout = int(data['timeout'])
    else:
        timeout = 10

    if 'lang_code' in data:
        lang_code = data['lang_code']
        language = Language.find(lang_code)

    user = flask.g.user

    # Start worker threads to get url contents
    contents = get_content_for_urls(urls, timeout)

    # If the user sends along the language, then compute the difficulty
    if language is not None:
        for each_content_dict in contents:
                difficulty = user.text_difficulty(each_content_dict["content"], language)
                each_content_dict["difficulty"] = difficulty

    return json_result(dict(contents=contents))
