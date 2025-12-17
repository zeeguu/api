import newspaper
from urllib.parse import urlparse

from .feed_handler import FeedHandler

from zeeguu.logging import log

# URL path patterns that typically indicate non-article pages
NON_ARTICLE_PATH_PATTERNS = [
    '/manual', '/style', '/about', '/contact', '/privacy', '/terms',
    '/login', '/register', '/signup', '/account', '/profile',
    '/search', '/tag/', '/tags/', '/category/', '/categories/',
    '/author/', '/authors/', '/archive/', '/archives/',
    '/rss', '/feed', '/sitemap', '/robots',
    '/cookie', '/legal', '/help', '/faq', '/support',
    '/advertise', '/advertising', '/sponsor',
    '/subscribe', '/newsletter', '/unsubscribe',
]

# Subdomain patterns that typically indicate non-article pages
# (Many sites use subdomains for article categories like sports.example.com, so we only block specific patterns)
NON_ARTICLE_SUBDOMAIN_PATTERNS = [
    'manual', 'style', 'help', 'support', 'faq',
    'login', 'auth', 'account', 'accounts', 'my',
    'api', 'cdn', 'static', 'assets', 'images', 'img', 'media',
    'mail', 'email', 'smtp',
    'admin', 'cms', 'dashboard',
    'shop', 'store', 'tienda', 'boutique',
    'ads', 'advertising', 'publicidad',
]


def _create_newspaper_config():
    """Create a newspaper config with proper browser-like headers."""
    config = newspaper.Config()
    config.fetch_images = False
    config.request_timeout = 10
    config.browser_user_agent = (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    # newspaper3k doesn't have direct Accept header config, but User-Agent helps
    return config


class NewspaperFeed(FeedHandler):
    def __init__(
        self,
        url: str,
        feed_type: int,
        use_cache: bool = True,
        is_stored_db: bool = False,
    ):
        self.use_cache = use_cache
        super().__init__(url, feed_type)
        self._config = _create_newspaper_config()
        log(f"Using Newspaper Handler ({self.url})")

    def extract_feed_metadata(self) -> None:
        print("Extracting Feed Metadata.")
        data = newspaper.Source(self.url)
        self.title = data.brand
        self.description = data.description
        self.image_url_string = data.favicon

    def _is_likely_article_url(self, url: str) -> bool:
        """
        Filter out URLs that are unlikely to be articles.

        Returns False for:
        - Subdomains matching non-article patterns (e.g., manualdeestilo.*, help.*, api.*)
        - Non-article paths (style guides, about pages, etc.)
        - URLs without meaningful path components
        """
        try:
            parsed = urlparse(url)
            url_domain = parsed.netloc.lower()
            url_path = parsed.path.lower()

            # Check for non-article subdomain patterns
            # Extract subdomain by removing www. and comparing to base domain
            for pattern in NON_ARTICLE_SUBDOMAIN_PATTERNS:
                if url_domain.startswith(f"{pattern}.") or f".{pattern}." in url_domain:
                    log(f"   Skipping non-article subdomain '{pattern}': {url}")
                    return False

            # Check for non-article path patterns
            for pattern in NON_ARTICLE_PATH_PATTERNS:
                if pattern in url_path:
                    log(f"   Skipping non-article pattern '{pattern}': {url}")
                    return False

            # Skip URLs with no meaningful path (just homepage)
            if url_path in ['', '/', '/index.html', '/index.php']:
                log(f"   Skipping homepage URL: {url}")
                return False

            return True
        except Exception as e:
            log(f"   Error parsing URL {url}: {e}")
            return False

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
            news_feed = newspaper.build(self.url, config=self._config, request_timeout=30)
        else:
            print("NOT skipping cached articles...")
            news_feed = newspaper.build(
                self.url, config=self._config, memoize_articles=False, request_timeout=30
            )

        all_articles = news_feed.articles
        log(f"** Total URLs discovered: {len(all_articles)}")

        # Filter to likely article URLs before downloading
        articles_to_process = [a for a in all_articles if self._is_likely_article_url(a.url)]
        log(f"** Articles after filtering: {len(articles_to_process)}")

        feed_items = []
        for article in articles_to_process:
            try:
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
            except newspaper.ArticleException as e:
                # Article-specific errors (download failed, parse failed)
                log(f"   Article error for {article.url}: {e}")
            except Exception as e:
                error_msg = str(e).lower()
                if '406' in error_msg:
                    log(f"   HTTP 406 (Not Acceptable) - server rejected request: {article.url}")
                elif '403' in error_msg:
                    log(f"   HTTP 403 (Forbidden) - access denied: {article.url}")
                elif '404' in error_msg:
                    log(f"   HTTP 404 (Not Found): {article.url}")
                elif 'timeout' in error_msg:
                    log(f"   Timeout downloading: {article.url}")
                else:
                    log(f"   Failed to process {article.url}: {e}")

        return feed_items
