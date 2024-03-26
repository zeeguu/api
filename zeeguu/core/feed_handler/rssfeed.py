import feedparser
import requests

from .feed_handler import FeedHandler
from zeeguu.logging import log, logp


class RSSFeed(FeedHandler):
    def __init__(self, url: str, feed_type: int):
        super().__init__(url, feed_type)

    def extract_feed_metadata(self) -> None:
        data = feedparser.parse(self.url)
        try:
            title = data.feed.title
        except:
            title = ""
        try:
            description = data.feed.subtitle
        except:
            description = ""
        self.title = title
        self.description = description
        self.image_url_string = ""

        try:
            image_url_string = data.feed.image.href
            print(f"Found image url at: {image_url_string}")
        except:
            print("Could not find any image url.")

    def get_feed_articles(self) -> list[dict]:
        """
        Returns a list[dictionary] containing the following fields:
            title:str, the title of the article
            url:str, the url to the article
            content:str, the content of the article
            summary:str, the summary of the article if available
            published_datetime:datetime, date time of the article
        """
        connect_timeout_seconds = 10
        read_timeout_seconds = 10

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36"
        }  # This is chrome, you can set whatever browser you like

        feed_items = []
        try:
            response = requests.get(self.url, headers=headers, timeout=(connect_timeout_seconds, read_timeout_seconds))
            feed_data = feedparser.parse(response.text)

            log(f"** Articles in feed: {len(feed_data.entries)}")
            for item in feed_data.entries:
                publish_time = self.get_server_time(item.get("published_parsed"))
                new_item_data_dict = dict(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    content=item.get("content", ""),
                    summary=item.get("summary", ""),
                    published_datetime=publish_time,
                )
                feed_items.append(new_item_data_dict)
        except requests.exceptions.ConnectTimeout as e:
            msg = f"Connection timeout when trying to connect to {self.url}"
            from sentry_sdk import capture_message
            print(msg)
            capture_message(msg)

        return feed_items
