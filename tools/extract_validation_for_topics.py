from zeeguu.core.model.article import Article
from zeeguu.core.model.language import Language
from zeeguu.api.app import create_app
import numpy as np

import zeeguu.core
import json

"""
    Extract small samples with and wihtout any topics for testing.
"""

db_session = zeeguu.core.model.db.session
app = create_app()
app.app_context().push()

valid_articles_da = (
    Article.query.filter(Article.language.has(Language.code == "da"))
    .filter(Article.topics.any())
    .filter(Article.url_keywords.any())
    .all()
)

valid_articles_es = (
    Article.query.filter(Article.language.has(Language.code == "es"))
    .filter(Article.topics.any())
    .filter(Article.url_keywords.any())
    .all()
)


def get_topics(a: Article):
    return ", ".join([t.title for t in a.topics])


def get_ordered_url_keywords(a: Article):
    url_keywords = [(uk.url_keywords.keyword, uk.rank) for uk in a.url_keywords]
    url_keywords = sorted(url_keywords, key=lambda x: x[1])
    return ", ".join([uk[0] for uk in url_keywords])


def get_article_dict(a: Article):
    return {
        "id": a.id,
        "title": a.title,
        "topics": get_topics(a),
        "url_keywords": get_ordered_url_keywords(a),
        "language": a.language.code,
        "summary": a.summary,
    }


# Set seed for deterministic sample
np.random.seed(0)
sample_da = np.random.choice(valid_articles_da, 200, replace=False)
sample_es = np.random.choice(valid_articles_es, 200, replace=False)


data_to_evalutate = [get_article_dict(a) for a in sample_da] + [
    get_article_dict(a) for a in sample_es
]

with open("data_for_eval.json", "w+", encoding="utf-8") as f:
    f.write(json.dumps(data_to_evalutate))


valid_articles_da = (
    Article.query.filter(Article.language.has(Language.code == "da"))
    .filter(~Article.topics.any())
    .filter(Article.broken == 0)
    .all()
)

valid_articles_es = (
    Article.query.filter(Article.language.has(Language.code == "es"))
    .filter(~Article.topics.any())
    .filter(Article.broken == 0)
    .all()
)

np.random.seed(0)
sample_da = np.random.choice(valid_articles_da, 200, replace=False)
sample_es = np.random.choice(valid_articles_es, 200, replace=False)

data_to_evalutate = [get_article_dict(a) for a in sample_da] + [
    get_article_dict(a) for a in sample_es
]

with open("data_for_eval_no_topic.json", "w+", encoding="utf-8") as f:
    f.write(json.dumps(data_to_evalutate))
