from .newspaperfeed import NewspaperFeed
from .rssfeed import RSSFeed

FEED_TYPE_TO_FEED_HANDLER = {
    0: RSSFeed,
    1: NewspaperFeed,
}

STANDARD_FEED_HANDLER = 0