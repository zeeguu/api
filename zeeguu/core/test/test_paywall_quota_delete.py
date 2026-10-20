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
from zeeguu.core.model import Article, ArticleTopicMap, SkippedUrl
from zeeguu.core.model.source_text import SourceText
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

    def _crawl_one_item(self, assess_and_summarize, feed=None, url="https://example.com/kultur/paywalled-story"):
        # The real download_feed_item, with the network, the models and the
        # LLM mocked out.
        feed = feed or FeedRule().feed
        crawl_report = CrawlReport()
        crawl_report.add_feed(feed)
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
            "assess_and_summarize": assess_and_summarize,
        }
        mocks = {name: MagicMock(side_effect=fn) for name, fn in patches.items()}
        self.downloads = mocks["readability_download_and_parse"]
        with patch.object(feed, "feed_items", return_value=items), patch.multiple(
            article_downloader, **mocks
        ):
            summary = article_downloader.download_from_feed(
                feed, session, crawl_report, save_in_elastic=False
            )
        return summary, crawl_report._get_feed_dict(feed), url, np_article

    def _crawl_over_quota_paywall(self, feed=None, **kwargs):
        llm = MagicMock(
            side_effect=Exception(
                "PAYWALL: Article appears to be incomplete due to paywall"
            )
        )
        with patch.object(
            article_downloader, "_should_save_paywall_sample", return_value=False
        ):
            result = self._crawl_one_item(
                lambda *a, **k: llm(), feed=feed, **kwargs
            )
        return result, llm

    def test_over_quota_paywall_leaves_only_a_skipped_url(self):
        # The LLM is asked before the article is created, so a paywall over
        # the day's sample quota has nothing to delete; what is left is the
        # note that it was skipped.
        (summary, report, url, np_article), _ = self._crawl_over_quota_paywall()

        assert summary.startswith("0 new articles")
        assert report["total_low_quality"] == 1
        assert Article.find(url) is None
        assert SourceText.query.filter_by(content=np_article.text).count() == 0
        assert SkippedUrl.find(url).reason == SkippedUrl.PAYWALL_OVER_SAMPLE_QUOTA

    def test_a_skipped_url_is_not_sent_to_the_llm_again(self):
        feed = FeedRule().feed
        self._crawl_over_quota_paywall(feed)

        (summary, report, _, _), llm = self._crawl_over_quota_paywall(feed)

        assert self.downloads.call_count == 0
        assert llm.call_count == 0
        assert report["total_in_db"] == 1

    def test_the_same_text_under_a_new_url_is_not_sent_to_the_llm_again(self):
        feed = FeedRule().feed
        self._crawl_over_quota_paywall(feed)

        renamed = "https://example.com/kultur/paywalled-story-updated-headline"
        (_, report, _, _), llm = self._crawl_over_quota_paywall(feed, url=renamed)

        assert llm.call_count == 0
        assert report["total_in_db"] == 1
        assert SkippedUrl.find(renamed) is not None

    def test_the_assessment_is_saved_on_the_article_created_after_it(self):
        assessment = {
            "original_cefr_level": "B1",
            "original_summary": "What the LLM wrote.",
            "article_type": "news",
            "is_disturbing": False,
            "provider": "test",
            "model_name": None,
        }

        summary, _, url, _ = self._crawl_one_item(lambda *a, **k: assessment)

        assert summary.startswith("1 new articles")
        article = Article.find(url)
        assert article.cefr_level == "B1"
        assert article.summary == "What the LLM wrote."
        assert not article.broken

    def test_only_old_skipped_urls_are_pruned(self):
        feed = FeedRule().feed
        self._crawl_over_quota_paywall(feed)
        old_url = "https://example.com/kultur/a-month-old-paywall"
        SkippedUrl.record(session, old_url, feed, None, SkippedUrl.PAYWALL_OVER_SAMPLE_QUOTA)
        SkippedUrl.find(old_url).skipped_at = datetime.now() - timedelta(days=31)
        session.commit()

        SkippedUrl.skipped_before(datetime.now() - timedelta(days=30)).delete(
            synchronize_session=False
        )

        assert SkippedUrl.find(old_url) is None
        assert SkippedUrl.query.count() == 1
