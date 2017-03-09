import Queue
import threading
import time

import flask
from flask import request
from zeeguu.language.text_difficulty import text_difficulty
from zeeguu.model import KnownWordProbability, Language
from zeeguu.the_librarian.page_content_extractor import PageExtractor

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
    queue = Queue.Queue()

    urls = []
    if 'urls' in data:
        for url in data['urls']:
            urls.append(url)
    else:
        return 'FAIL'

    if 'timeout' in data:
        timeout = int(data['timeout'])
    else:
        timeout = 10

    # Start worker threads to get url contents
    threads = []
    for url in urls:
        thread = threading.Thread(target=PageExtractor.worker, args=(url['url'], url['id'], queue))
        thread.daemon = True
        threads.append(thread)
        thread.start()

    # Wait for workers to finish until timeout
    stop = time.time() + timeout
    while any(t.isAlive() for t in threads) and time.time() < stop:
        time.sleep(0.1)

    contents = []
    for i in xrange(len(urls)):
        try:
            contents.append(queue.get_nowait())
        except Queue.Empty:
            pass

    # If the user sends along the language, then we can compute the difficulty
    if 'lang_code' in data:
        lang_code = data['lang_code']
        language = Language.find(lang_code)
        if language is not None:
            print "got language"
            user = flask.g.user
            known_probabilities = KnownWordProbability.find_all_by_user_cached(user)
            for each_content_dict in contents:
                    difficulty = text_difficulty(
                            each_content_dict["content"],
                            language,
                            known_probabilities
                            )
                    each_content_dict["difficulty"] = difficulty

    return json_result(dict(contents=contents))
