from .newspaperfeed import NewspaperFeed
from .rssfeed import RSSFeed

FEED_TYPE_TO_FEED_HANDLER = {
    0: RSSFeed,
    1: NewspaperFeed,
}

FEED_TYPE = {
    "rss": 0,
    "newspaper": 1,
}