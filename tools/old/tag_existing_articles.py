#!/usr/bin/env python

"""

    goes through all the articles in the DB 
    by language and associates them with the
    corresponding topics
    

"""

import zeeguu.core
from zeeguu.core.model import Article, Language, LocalizedTopic

db_session = zeeguu.core.model.db.session

counter = 0

languages = Language.available_languages()

for language in languages:
    articles = (
        Article.query.filter(Article.language == language)
        .order_by(Article.id.desc())
        .all()
    )

    loc_topics = LocalizedTopic.all_for_language(language)

    total_articles = len(articles)
    for article in articles:
        counter += 1
        for loc_topic in loc_topics:
            if loc_topic.matches_article(article):
                article.add_topic(loc_topic.topic)
                # print(f" #{loc_topic.topic_translated}: {article.url.as_string()}")
        db_session.add(article)
        if counter % 1000 == 0:
            percentage = (100 * counter / total_articles) / 100
            print(
                f"{counter} dorticles done ({percentage}%). last article id: {article.id}. comitting... "
            )
            db_session.commit()
