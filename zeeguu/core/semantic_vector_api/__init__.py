import os
from zeeguu.core.model import Article
import requests

EMB_API_CONN_STRING = os.environ.get(
    "ZEEGUU_EMB_API_CONN_STRING", "http://127.0.0.1:8000"
)


def get_embedding_from_article(a: Article):
    r = requests.post(
        url=f"{EMB_API_CONN_STRING}/get_article_embedding",
        json={"article_content": a.content},
    )
    print(r)
    return r.json()
