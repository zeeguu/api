#!/usr/bin/env python

"""

    goes through all the articles in the DB 
    for a given language and localized topic
    and tags them if they match

    used after the set of terms that define a
    localized topic has been updated


"""
import sys

import zeeguu.core
from zeeguu.core.model import Article, Language, LocalizedTopic


def update_particular_tag(language, loc_topic):
    counter = 0
    articles = (
        Article.query.filter(Article.language == language)
        .order_by(Article.id.desc())
        .all()
    )

    total_articles = len(articles)
    for article in articles:
        counter += 1
        if loc_topic.matches_article(article):
            article.add_topic(loc_topic.topic)
            print(f" #{loc_topic.topic_translated}: {article.url.as_string()}")
        db_session.add(article)
        if counter % 1000 == 0:
            percentage = (100 * counter / total_articles) / 100
            print(
                f"{counter} articles done ({percentage}%). last article id: {article.id}. comitting... "
            )
            db_session.commit()


if __name__ == "__main__":
    try:
        db_session = zeeguu.core.model.db.session

        language = Language.find(sys.argv[1])
        print(f"Tagging articles in {language}")

        loc_topics = LocalizedTopic.all_for_language(language)
        loc_topic = next(t for t in loc_topics if t.topic_translated == sys.argv[2])

        print(
            f"Updating info about localized_topic: {loc_topic.topic_translated, loc_topic.id}"
        )

    except IndexError:
        print(f"usage: {sys.argv[0]} lang_code localized_topic_name")
