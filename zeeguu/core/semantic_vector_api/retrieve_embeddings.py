import os
import requests
from zeeguu.core.model import Article


EMB_API_CONN_STRING = os.environ.get(
    "ZEEGUU_EMB_API_CONN_STRING", "http://127.0.0.1:8000"
)


def get_embedding_from_video(v):

    # TODO: At some point update the Embedding API to not talk only about articles
    r = requests.post(
        url=f"{EMB_API_CONN_STRING}/get_article_embedding",
        json={
            "article_content": v.get_content(),
            "article_language": v.language.name.lower(),
        },
    )
    return r.json()


def get_embedding_from_article(a: Article):
    r = requests.post(
        url=f"{EMB_API_CONN_STRING}/get_article_embedding",
        json={
            "article_content": a.get_content(),
            "article_language": a.language.name.lower(),
        },
    )
    return r.json()


def get_embedding_from_text(text: str, language: str = None):
    data = {
        "article_content": text,
    }
    if language:
        data["article_language"] = language
    try:
        r = requests.post(url=f"{EMB_API_CONN_STRING}/get_article_embedding", json=data, timeout=5)
        return r.json()
    except Exception as e:
        print(f"Warning: Embedding service unavailable: {e}")
        return None
