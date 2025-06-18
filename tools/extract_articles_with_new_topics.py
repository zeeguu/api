from zeeguu.core.model.article import Article
from zeeguu.api.app import create_app
from zeeguu.core.model.article_topic_map import ArticleTopicMap, TopicOriginType
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
    Article.query.join(ArticleTopicMap)
    .filter(ArticleTopicMap.origin_type != TopicOriginType.INFERRED)
    .all()
)

articles_to_extract = []
for a in tqdm(articles, total=len(articles)):
    tuple = [a.id, a.get_content(), len(a.topics)]
    topics_data = []
    for atm in a.topics:
        topics_data += [atm.topic.title, atm.origin_type]
    articles_to_extract.append((tuple + topics_data))

with open("data_for_eval_new_topic.json", "w+", encoding="utf-8") as f:
    f.write(json.dumps(articles_to_extract))
