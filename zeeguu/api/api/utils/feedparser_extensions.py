# This file contains utilities that
from bs4 import BeautifulSoup
import urllib.request, urllib.error, urllib.parse
import feedparser


def list_of_feeds_at_url(domain):
    """
    a list of feeds that can be found at the given url,
    or an empty list if something goes wrong
    :param domain:
    :return:
    """
    try:
        feed_data = []
        page = urllib.request.urlopen(domain)
        soup = BeautifulSoup(page, "lxml")
        feed_urls = soup.findAll("link", type="application/rss+xml")

        for feed_url in feed_urls:
            feed_url = feed_url["href"]
            if feed_url[0] == "/":
                feed_url = domain + feed_url

            feed = feedparser.parse(feed_url).feed

            feed_data.append(
                {
                    "url": feed_url,
                    "title": feed.get("title", ""),
                    "description": feed.get("description", ""),
                    "image_url": feed.get("image", ""),
                    "language": feed.get("language", ""),
                }
            )

        return feed_data

    except Exception as e:
        # print e
        return []


def two_letter_language_code(feed):
    """
        feed.language conforms to
        http://www.rssboard.org/rss-language-codes
        sometimes it is of the form de-de, de-au providing a hint of dialect
        thus, we only pick the first two letters of this code

    :param feed:
    :return:
    """
    return feed.language[:2]
