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
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import zeeguu.core
from zeeguu.core.content_retriever import article_downloader
from zeeguu.core.model import Article, ArticleTopicMap
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

    def test_a_later_failure_does_not_undo_an_earlier_article(self):
        # download_feed_item leaves the last of an article's work (fragments,
        # tokenization cache) pending. The rollback for a failing item that
        # comes after it in the feed must not take that work with it.
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
            for i, name in enumerate(["works", "fails"])
        ]
        survivor = ArticleRule().article

        def download_feed_item(session, feed, feed_item, url, *args, **kwargs):
            if feed_item["title"] == "fails":
                raise ConnectionError("readability server went away")
            # stands in for the fragments + cache, added but not committed
            survivor.add_topic_if_doesnt_exist(
                self.topic, session, TopicOriginType.INFERRED.value
            )
            return survivor

        with patch.object(feed, "feed_items", return_value=items), patch.object(
            article_downloader, "_url_after_redirects", side_effect=lambda u: u
        ), patch.object(
            article_downloader, "download_feed_item", side_effect=download_feed_item
        ):
            article_downloader.download_from_feed(
                feed, session, crawl_report, save_in_elastic=False
            )

        session.rollback()
        assert ArticleTopicMap.query.filter_by(article_id=survivor.id).count() == 1

    def test_over_quota_paywall_is_deleted_and_skipped(self):
        # The real download_feed_item, from the download up to the LLM saying
        # "paywall" with the day's sample quota already full.
        feed = FeedRule().feed
        crawl_report = CrawlReport()
        crawl_report.add_feed(feed)
        url = "https://example.com/kultur/paywalled-story"
        items = [
            {
                "url": url,
                "title": "Paywalled story",
                "summary": "",
                "published_datetime": datetime.now(),
            }
        ]
        np_article = SimpleNamespace(
            text="Only the teaser is visible. " * 20,
            authors=[],
            htmlContent="<p>Only the teaser is visible.</p>",
        )

        def paywall(*args, **kwargs):
            raise Exception("PAYWALL: Article appears to be incomplete due to paywall")

        patches = {
            "_url_after_redirects": lambda u: u,
            "readability_download_and_parse": lambda u: np_article,
            "is_duplicate_by_simhash": lambda *a: (False, None),
            "sufficient_quality": lambda *a: (True, "", None),
            "cleanup_text_w_crawl_report": lambda text, *a: text,
            "extract_article_image": lambda *a: None,
            "get_topic_classification_based_on_similar_content": lambda *a, **k: self.topic,
            "is_advertorial": lambda **k: (False, None),
            "is_disturbing_content_based_on_keywords": lambda **k: (False, None),
            "assess_summarize_and_classify": paywall,
            "simplify_and_classify": paywall,
            "_should_save_paywall_sample": lambda *a: False,
        }
        with patch.object(feed, "feed_items", return_value=items), patch.multiple(
            article_downloader,
            SIMPLIFY_AT_CRAWL=False,
            **{name: MagicMock(side_effect=fn) for name, fn in patches.items()},
        ):
            summary = article_downloader.download_from_feed(
                feed, session, crawl_report, save_in_elastic=False
            )

        assert summary.startswith("0 new articles")
        assert crawl_report._get_feed_dict(feed)["total_low_quality"] == 1
        assert Article.find(url) is None
