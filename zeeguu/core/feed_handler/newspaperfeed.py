import newspaper
from .feed_handler import FeedHandler

from zeeguu.logging import log, logp


class NewspaperFeed(FeedHandler):
    def __init__(self, url: str, feed_type: int, use_cache: bool = True):
        self.use_cache = use_cache
        super().__init__(url, feed_type)
        logp(f"Created Newspaper Source ({self.url})")

    def extract_feed_metadata(self) -> None:
        data = newspaper.Source(self.url)
        self.title = data.brand
        self.description = data.description
        self.image_url_string = data.favicon

    def get_feed_articles(self) -> list[dict]:
        """
        Returns a list[dictionary] containing the following fields:
            title:str, the title of the article
            url:str, the url to the article
            content:str, the content of the article
            summary:str, the summary of the article if available
            published_datetime:datetime, date time of the article
        """
        print("Newspaper Built!")
        # Not sure if we should use cache (as currently the crawler checks if the article is in)
        # This makes it complicated to assign a feed and download the articles found at that time.
        # Currently, it ignores the newspaper's cache and justs uses ours.
        if self.use_cache:
            news_feed = newspaper.build(self.url)
        else:
            news_feed = newspaper.build(self.url, memoize_articles=False)
        feed_data = news_feed.articles

        feed_items = []
        log(f"** Articles in feed: {len(feed_data)}")
        for article in feed_data:
            article.download()
            article.parse()
            publish_date = self.get_server_time(article.publish_date)

            new_item_data_dict = dict(
                title=article.title,
                url=article.url,
                content=article.text,
                summary=article.summary,
                published_datetime=publish_date,
            )
            feed_items.append(new_item_data_dict)

        return feed_items
