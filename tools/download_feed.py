from zeeguu.operations.crawler.crawl_report import CrawlReport
from zeeguu.operations.crawler.feed_retrieval import download_for_feeds
from zeeguu.core.model import Feed
from zeeguu.api.app import create_app_for_scripts

app = create_app_for_scripts()
app.app_context().push()

crawl_report = CrawlReport()

feed = Feed.find_by_id(85)
download_for_feeds([feed], crawl_report)
