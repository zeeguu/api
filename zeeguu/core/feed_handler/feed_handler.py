import time
from datetime import datetime, timezone, timedelta
from zeeguu.core.util.time import normalize_to_server_time


class FeedHandler:
    def __init__(self, url: str, feed_type: int):
        self.url = url
        self.feed_type = feed_type
        self.title = ""
        self.description = ""
        self.image_url_string = ""

    def get_server_time(self, article_date) -> datetime:
        # feedparser gives its *_parsed dates as a UTC struct_time, not a
        # datetime. Without this every RSS item was dated now(), which also
        # turned off the feed's last_crawled_time filter (Jan 2024 – Oct 2026).
        if isinstance(article_date, time.struct_time):
            article_date = datetime(*article_date[:6], tzinfo=timezone.utc)
        if type(article_date) is datetime:
            return normalize_to_server_time(article_date)
        return datetime.now()

    def extract_feed_metadata() -> None:
        """
        Performs the logic to fill the properties of the
        object. These are accessed from the other classes.
        """
        NotImplementedError

    def get_feed_articles(self) -> list[dict]:
        """
        Returns a list[dictionary] containing the following fields:
            title:str, the title of the article
            url:str, the url to the article
            content:str, the content of the article
            summary:str, the summary of the article if available
            published:str, the date of the article as string
            published_datetime:datetime, date time of the article
        """
        NotImplementedError
