"""
Uploading a portal or front page (Wikipedia.nl's front page gave four
newlines of text) used to reach language detection with no words, fail it,
and come back as "406 Language not supported". It is a page with no article
text: say so, with a 422 the client can show.
"""

from zeeguu.api.test.fixtures import logged_in_client


def test_whitespace_only_upload_is_rejected_as_no_text(logged_in_client):
    response = logged_in_client.response_from_post(
        "/article_upload/create",
        data=dict(
            url="https://www.wikipedia.nl/",
            text_content="\n\n\n\n",
            raw_html="<div>\n\n\n\n</div>",
            title="Wikipedia.nl",
        ),
    )
    assert response.status_code == 422
    assert "article text" in response.get_json()["message"]
