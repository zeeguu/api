from datetime import datetime, timedelta
from random import randint

from zeeguu.core.test.rules.base_rule import BaseRule
from zeeguu.core.test.rules.language_rule import LanguageRule
from zeeguu.core.test.rules.rss_feed_rule import RSSFeedRule
from zeeguu.core.test.rules.url_rule import UrlRule
from zeeguu.core.model import Article
from zeeguu.core.test.test_data.mocking_the_web import url_diesel_fahrverbote


class ArticleRule(BaseRule):
    """

    Creates an Article object with random data and saves it to the database.

    """

    def __init__(self, real=False):
        super().__init__()

        if real:
            self.article = Article.find_or_create(
                ArticleRule.db.session, url_diesel_fahrverbote
            )
        else:
            self.article = self._create_model_object()
            self.save(self.article)

    def _create_model_object(self):
        title = " ".join(self.faker.text().split()[:4])
        authors = self.faker.name()
        content = self.faker.text()
        summary = self.faker.text()
        published = datetime.now() - timedelta(minutes=randint(0, 7200))
        rss_feed = RSSFeedRule().feed
        language = LanguageRule().random
        url = UrlRule().url

        article = Article(
            url, title, authors, content, summary, published, None, rss_feed, language
        )

        if self._exists_in_db(article):
            return self._create_model_object()

        return article

    @staticmethod
    def _exists_in_db(obj):
        return Article.exists(obj)
