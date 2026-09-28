import pytest

from zeeguu.api.endpoints.nlp import SpacyEndpointsRemoved
from zeeguu.api.test.fixtures import logged_in_client


@pytest.mark.parametrize(
    "endpoint",
    [
        "/do_some_spacy",
        "/create_confusion_words",
        "/annotate_clues",
        "/get_shorter_similar_sents_in_article",
        "/get_smaller_context",
    ],
)
def test_removed_spacy_endpoints_fail_loudly(logged_in_client, endpoint):
    # app.testing propagates the exception instead of turning it into a 500
    with pytest.raises(SpacyEndpointsRemoved):
        logged_in_client.response_from_post(endpoint, data={"language": "da"})
