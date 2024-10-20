from zeeguu.core.model import Article
from zeeguu.api.app import create_app
from zeeguu.core.model.new_article_topic_map import NewArticleTopicMap, TopicOriginType
import numpy as np
from tqdm import tqdm

import zeeguu.core
import json

"""
    Export Articles which have been given a topic based on url_keywords or hardcoded.
    This can be used to explore the data and run different inference methods.
"""

db_session = zeeguu.core.model.db.session
app = create_app()
app.app_context().push()

articles = (
    Article.query.join(NewArticleTopicMap)
    .filter(NewArticleTopicMap.origin_type != TopicOriginType.INFERRED)
    .all()
)

articles_to_extract = []
for a in tqdm(articles, total=len(articles)):
    tuple = (
        a.id,
        a.content,
        a.new_topics_as_string(),
        a.new_topics[-1].new_topic.title,
    )
    articles_to_extract.append(tuple)

with open("data_for_eval_new_topic.json", "w+", encoding="utf-8") as f:
    f.write(json.dumps(articles_to_extract))
