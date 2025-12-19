#!/usr/bin/env python
"""
Fix Feed - diagnose, repair, or deactivate broken feeds.

Finds feeds by domain, discovers working RSS URLs, and updates the feed configuration.

Usage:
    python -m tools.fix_feed --domain "lespresso.it"
    python -m tools.fix_feed --domain "elperiodico" --dry-run
    python -m tools.fix_feed --id 194
    python -m tools.fix_feed --id 194 --deactivate
    python -m tools.fix_feed --id 194 --activate
    python -m tools.fix_feed --title "Tom Standage"
    python -m tools.fix_feed --id 75 --discover "elpais.es"
"""

import argparse
import requests
from urllib.parse import urlparse

from zeeguu.api.app import create_app
from zeeguu.core.model import Feed, db
from zeeguu.core.model.url import Url
from zeeguu.core.model.domain_name import DomainName

app = create_app()
app.app_context().push()

# Common RSS feed paths to try
RSS_PATHS = [
    "/feed",
    "/rss",
    "/rss.xml",
    "/feed.xml",
    "/atom.xml",
    "/feeds/posts/default",
    "/index.xml",
]

FEED_TYPE_NAMES = {
    0: "RSSFeed",
    1: "NewspaperFeed",
}


def find_feeds_by_domain(domain_query: str):
    """Find feeds matching a domain pattern."""
    feeds = (
        Feed.query
        .join(Url, Feed.url_id == Url.id)
        .join(DomainName, Url.domain_name_id == DomainName.id)
        .filter(DomainName.domain_name.contains(domain_query))
        .all()
    )
    return feeds


def find_feeds_by_title(title_query: str):
    """Find feeds matching a title pattern (case-insensitive)."""
    return Feed.query.filter(Feed.title.ilike(f"%{title_query}%")).all()


def find_feed_by_id(feed_id: int):
    """Find a feed by ID."""
    return Feed.query.get(feed_id)


def check_rss_url(url: str) -> tuple[bool, str]:
    """Check if a URL returns valid RSS/XML content."""
    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; ZeeguuBot/1.0)'
        })
        if response.status_code != 200:
            return False, f"{response.status_code}"

        content_type = response.headers.get('content-type', '').lower()
        content_start = response.text[:500].lower()

        is_xml = (
            'xml' in content_type or
            'rss' in content_type or
            '<?xml' in content_start or
            '<rss' in content_start or
            '<feed' in content_start
        )

        if is_xml:
            return True, "valid RSS"
        else:
            return False, f"not RSS (content-type: {content_type})"
    except requests.RequestException as e:
        return False, str(e)


def discover_rss_from_html(url: str) -> list[str]:
    """Find RSS links in HTML <link> tags."""
    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; ZeeguuBot/1.0)'
        })
        if response.status_code != 200:
            return []

        # Look for <link rel="alternate" type="application/rss+xml" href="...">
        import re
        rss_links = re.findall(
            r'<link[^>]+rel=["\']alternate["\'][^>]+type=["\']application/rss\+xml["\'][^>]+href=["\']([^"\']+)["\']',
            response.text, re.IGNORECASE
        )
        # Also try reversed order (href before type)
        rss_links += re.findall(
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+type=["\']application/rss\+xml["\']',
            response.text, re.IGNORECASE
        )
        return list(set(rss_links))  # dedupe
    except requests.RequestException:
        return []


def discover_rss_feeds(base_domain: str) -> list[tuple[str, bool, str]]:
    """Try common RSS paths and HTML discovery, return results."""
    results = []

    # Ensure domain has scheme
    if not base_domain.startswith('http'):
        base_domain = f"https://{base_domain}"

    # Remove trailing slash
    base_domain = base_domain.rstrip('/')

    # First, try to find RSS links in HTML
    html_feeds = discover_rss_from_html(base_domain)
    for url in html_feeds:
        is_valid, status = check_rss_url(url)
        results.append((url, is_valid, f"from HTML: {status}"))

    # Then try common paths
    for path in RSS_PATHS:
        url = f"{base_domain}{path}"
        is_valid, status = check_rss_url(url)
        results.append((url, is_valid, status))

    return results


def deactivate_feed(feed: Feed, dry_run: bool = False):
    """Deactivate a feed."""
    if dry_run:
        print(f"  [DRY RUN] Would deactivate feed {feed.id} ({feed.title})")
        return

    feed.deactivated = 1
    db.session.commit()
    print(f"  ✓ Deactivated feed {feed.id} ({feed.title})")


def activate_feed(feed: Feed, dry_run: bool = False):
    """Activate a feed."""
    if dry_run:
        print(f"  [DRY RUN] Would activate feed {feed.id} ({feed.title})")
        return

    feed.deactivated = 0
    db.session.commit()
    print(f"  ✓ Activated feed {feed.id} ({feed.title})")


def update_feed_url(feed: Feed, new_url: str, dry_run: bool = False):
    """Update feed to use new URL and switch to RSS type."""
    parsed = urlparse(new_url)
    domain_str = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path or "/"

    if dry_run:
        print(f"  [DRY RUN] Would update feed {feed.id}:")
        print(f"    - New domain: {domain_str}")
        print(f"    - New path: {path}")
        print(f"    - New feed_type: 0 (RSSFeed)")
        return

    # Find or create domain
    domain = DomainName.find_or_create(db.session, domain_str)

    # Check if URL already exists
    existing_url = Url.query.filter_by(
        domain_name_id=domain.id,
        path=path
    ).first()

    if existing_url:
        feed.url_id = existing_url.id
    else:
        new_url_obj = Url(new_url, title=feed.title)
        db.session.add(new_url_obj)
        db.session.flush()
        feed.url_id = new_url_obj.id

    feed.feed_type = 0  # RSSFeed
    db.session.commit()
    print(f"  ✓ Updated feed {feed.id} to use {new_url} (RSSFeed)")


def main():
    parser = argparse.ArgumentParser(description="Fix broken feeds")
    parser.add_argument("--domain", type=str, help="Search for feeds by domain (partial match)")
    parser.add_argument("--title", type=str, help="Search for feeds by title (partial match, case-insensitive)")
    parser.add_argument("--id", type=int, help="Find feed by ID")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--auto", action="store_true", help="Automatically apply first valid RSS URL found")
    parser.add_argument("--deactivate", action="store_true", help="Deactivate the feed(s)")
    parser.add_argument("--activate", action="store_true", help="Activate the feed(s)")
    parser.add_argument("--discover", type=str, help="Domain to search for RSS feeds (e.g. 'elpais.es')")
    args = parser.parse_args()

    if args.deactivate and args.activate:
        parser.error("Cannot use both --deactivate and --activate")

    if not args.domain and not args.id and not args.title:
        parser.error("One of --domain, --title, or --id is required")

    # Find feeds
    if args.id:
        feed = find_feed_by_id(args.id)
        feeds = [feed] if feed else []
    elif args.title:
        feeds = find_feeds_by_title(args.title)
    else:
        feeds = find_feeds_by_domain(args.domain)

    if not feeds:
        print(f"No feeds found matching query")
        return

    for feed in feeds:
        print(f"\n{'='*60}")
        print(f"Feed: {feed.title} (id={feed.id})")
        print(f"  Language: {feed.language.code}")
        print(f"  Type: {FEED_TYPE_NAMES.get(feed.feed_type, f'Unknown({feed.feed_type})')}")
        print(f"  Deactivated: {bool(feed.deactivated)}")
        print(f"  Current URL: {feed.url.as_string() if feed.url else 'None'}")

        # Handle deactivate/activate commands
        if args.deactivate:
            deactivate_feed(feed, args.dry_run)
            continue
        if args.activate:
            activate_feed(feed, args.dry_run)
            continue

        current_valid = False
        if feed.url:
            # Check current URL
            current_valid, current_status = check_rss_url(feed.url.as_string())
            status_icon = "✓" if current_valid else "✗"
            print(f"  Current URL status: {status_icon} {current_status}")

        # If current URL works and no explicit --discover, skip
        if current_valid and not args.discover:
            print(f"\n  ✓ Feed is healthy, no action needed.")
            continue

        # Get base domain for discovery
        if args.discover:
            base_domain = args.discover
            if not base_domain.startswith('http'):
                base_domain = f"https://{base_domain}"
        elif feed.url:
            parsed = urlparse(feed.url.as_string())
            base_domain = f"{parsed.scheme}://{parsed.netloc}"
        else:
            continue

        print(f"\n  Discovering RSS feeds at {base_domain}...")
        results = discover_rss_feeds(base_domain)

        valid_urls = []
        for url, is_valid, status in results:
            icon = "✓" if is_valid else "✗"
            print(f"    {icon} {url} ({status})")
            if is_valid:
                valid_urls.append(url)

        if not valid_urls:
            print(f"\n  ⚠ No valid RSS feeds found at {base_domain}.")
            print(f"     Try: python -m tools.fix_feed --id {feed.id} --discover <other-domain>")
            continue

        if args.auto and valid_urls:
            update_feed_url(feed, valid_urls[0], args.dry_run)
        elif valid_urls and not args.dry_run:
            print(f"\n  Valid RSS URLs found:")
            for i, url in enumerate(valid_urls, 1):
                print(f"    {i}. {url}")

            choice = input(f"\n  Update feed to use which URL? (1-{len(valid_urls)}, or 'n' to skip): ")
            if choice.isdigit() and 1 <= int(choice) <= len(valid_urls):
                update_feed_url(feed, valid_urls[int(choice) - 1], args.dry_run)
            else:
                print("  Skipped.")


if __name__ == "__main__":
    main()
