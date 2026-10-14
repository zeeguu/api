"""
Deleting a freshly crawled article after the daily paywall-sample quota is full.

By the time the LLM says "paywall", download_feed_item has already given the
article its ArticleTopicMap and ArticleUrlKeywordMap rows. Deleting it used to
fail in the ORM: the relationships had passive_deletes but no delete cascade,
so SQLAlchemy tried to NULL the maps' article_id, which is part of their
primary key ("tried to blank-out primary key column"). Nothing rolled the
session back, so the next access to the feed raised PendingRollbackError and
the crawler abandoned the rest of the feed.
"""
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch

import zeeguu.core
from zeeguu.core.content_retriever import article_downloader
from zeeguu.core.model import ArticleTopicMap
from zeeguu.core.model.article_url_keyword_map import ArticleUrlKeywordMap
from zeeguu.core.model.url_keyword import UrlKeyword
from zeeguu.core.model.article_topic_map import TopicOriginType
from zeeguu.core.test.model_test_mixin import ModelTestMixIn
from zeeguu.core.test.rules.article_rule import ArticleRule
from zeeguu.core.test.rules.feed_rule import FeedRule
from zeeguu.core.test.rules.topic_rule import TopicRule
from zeeguu.operations.crawler.crawl_report import CrawlReport

session = zeeguu.core.model.db.session


class PaywallQuotaDeleteTest(ModelTestMixIn, TestCase):
    def setUp(self):
        super().setUp()
        self.article = ArticleRule().article
        self.topic = TopicRule.get_or_create_topic(2)

    def _give_it_topics_and_url_keywords(self, article):
        # What download_feed_item has done by the time the LLM runs.
        article.add_topic_if_doesnt_exist(
            self.topic, session, TopicOriginType.INFERRED.value
        )
        keyword = UrlKeyword.find_or_create(session, "kultur", article.language)
        article.set_url_keywords([keyword], session)
        session.flush()
        assert article.topics and article.url_keywords

    def test_deleting_an_article_with_topics_and_url_keywords(self):
        self._give_it_topics_and_url_keywords(self.article)
        article_id = self.article.id

        session.delete(self.article)
        session.commit()

        assert ArticleTopicMap.query.filter_by(article_id=article_id).count() == 0
        assert (
            ArticleUrlKeywordMap.query.filter_by(article_id=article_id).count() == 0
        )

    def test_a_failed_article_does_not_poison_the_rest_of_the_feed(self):
        feed = FeedRule().feed
        crawl_report = CrawlReport()
        crawl_report.add_feed(feed)
        now = datetime.now()
        items = [
            {
                "url": f"https://example.com/{name}",
                "title": name,
                "summary": "",
                "published_datetime": now - timedelta(minutes=i),
            }
            for i, name in enumerate(["fails", "works"])
        ]
        survivor = ArticleRule().article

        def download_feed_item(session, feed, feed_item, url, *args, **kwargs):
            if feed_item["title"] == "fails":
                # Any flush failure leaves the session needing a rollback.
                session.add(ArticleTopicMap(self.article, self.topic, 1))
                session.add(ArticleTopicMap(self.article, self.topic, 1))
                session.flush()
            return survivor

        with patch.object(feed, "feed_items", return_value=items), patch.object(
            article_downloader, "_url_after_redirects", side_effect=lambda u: u
        ), patch.object(
            article_downloader, "download_feed_item", side_effect=download_feed_item
        ):
            summary = article_downloader.download_from_feed(
                feed, session, crawl_report, save_in_elastic=False
            )

        assert summary.startswith("1 new articles")
