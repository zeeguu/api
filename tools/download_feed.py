from tools.crawl_summary.crawl_report import CrawlReport
from tools.feed_retrieval import download_for_feeds
from zeeguu.core.model.feed import Feed
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

crawl_report = CrawlReport()

feed = Feed.find_by_id(85)
download_for_feeds([feed], crawl_report)
