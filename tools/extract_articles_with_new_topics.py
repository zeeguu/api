from zeeguu.core.model import Article
from zeeguu.api.app import create_app
from zeeguu.core.model.new_article_topic_map import NewArticleTopicMap
import numpy as np
from tqdm import tqdm

import zeeguu.core
import json

db_session = zeeguu.core.model.db.session
app = create_app()
app.app_context().push()

articles = Article.query.all()

articles_to_extract = []
for a in tqdm(articles, total=len(articles)):
    if a.contains_new_topic_from_url():
        tuple = (
            a.id,
            a.content,
            a.new_topics_as_string(),
            a.new_topics[-1].new_topic.title,
        )
        articles_to_extract.append(tuple)

with open("data_for_eval_new_topic.json", "w+", encoding="utf-8") as f:
    f.write(json.dumps(articles_to_extract))
