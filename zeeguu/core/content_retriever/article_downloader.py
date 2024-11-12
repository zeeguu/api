"""

    Goes through all the interesting sources that the server knows
    about and downloads new articles saving them in the DB.  


"""

import newspaper
from collections import Counter
from time import time
from pymysql import DataError

from zeeguu.core.content_retriever.crawler_exceptions import *
from zeeguu.logging import log, logp

from zeeguu.core import model

SEMANTIC_SEARCH_AVAILABLE = True
try:
    from zeeguu.core.semantic_search import add_topics_based_on_semantic_hood_search
except:
    SEMANTIC_SEARCH_AVAILABLE = False
    print("######### Failed to load semantic search modules")
from zeeguu.core.content_quality.quality_filter import sufficient_quality
from zeeguu.core.content_cleaning import cleanup_text_w_crawl_report
from zeeguu.core.emailer.zeeguu_mailer import ZeeguuMailer
from zeeguu.core.model import Url, Feed, UrlKeyword, NewTopic
from zeeguu.core.model.new_article_topic_map import TopicOriginType
import requests

from zeeguu.core.model.article import MAX_CHAR_COUNT_IN_SUMMARY

from sentry_sdk import capture_exception as capture_to_sentry
from zeeguu.core.elastic.indexing import index_in_elasticsearch

from zeeguu.core.content_retriever import (
    readability_download_and_parse,
)

TIMEOUT_SECONDS = 10


import zeeguu

LOG_CONTEXT = "FEED RETRIEVAL"


def _url_after_redirects(url):
    # solve redirects and save the clean url
    response = requests.get(url)
    return response.url


def _date_in_the_future(time):
    from datetime import datetime

    return time > datetime.now()


def banned_url(url):
    banned = [
        "https://www.dr.dk/sporten/seneste-sport/",
        "https://www.dr.dk/nyheder/seneste/",
        # Old Text interface for TVs
        "https://www1.wdr.de/wdrtext/",
        # Videos
        "https://www.tagesschau.de/multimedia",
        "https://www.1jour1actu.com/non-classe",
        # Paywalled articles:
        "https://www.faz.net/pro",
    ]
    for each in banned:
        if url.startswith(each):
            return True
    return False


def download_from_feed(
    feed: Feed, session, crawl_report, limit=1000, save_in_elastic=True
):
    """

    Session is needed because this saves stuff to the DB.


    last_crawled_time is useful because otherwise there would be a lot of time
    wasted trying to retrieve the same articles, especially the ones which
    can't be retrieved, so they won't be cached.


    """

    summary_stream = ""
    start_feed_time = time()
    downloaded = 0
    downloaded_titles = []
    skipped_due_to_low_quality = 0
    skipped_already_in_db = 0

    last_retrieval_time_from_DB = None
    last_retrieval_time_seen_this_crawl = None

    if feed.last_crawled_time:
        last_retrieval_time_from_DB = feed.last_crawled_time
        log(f"LAST CRAWLED::: {last_retrieval_time_from_DB}")

    try:
        items = feed.feed_items(last_retrieval_time_from_DB)
    except Exception as e:
        import traceback

        traceback.print_stack()
        capture_to_sentry(e)
        return ""

    skipped_already_in_db = 0
    for feed_item in items:

        if downloaded >= limit:
            break

        feed_item_timestamp = feed_item["published_datetime"]

        if _date_in_the_future(feed_item_timestamp):
            log("Article from the future!")
            continue

        if (not last_retrieval_time_seen_this_crawl) or (
            feed_item_timestamp > last_retrieval_time_seen_this_crawl
        ):
            last_retrieval_time_seen_this_crawl = feed_item_timestamp
            crawl_report.set_feed_last_article_date(feed, feed_item_timestamp)

        if last_retrieval_time_seen_this_crawl > feed.last_crawled_time:
            crawl_report.set_feed_last_article_date(feed, feed_item_timestamp)
            feed.last_crawled_time = last_retrieval_time_seen_this_crawl
            session.add(feed)
            session.commit()

        logp(feed_item["url"])
        # check if the article is already in the DB
        art = model.Article.find(feed_item["url"])
        if art:
            skipped_already_in_db += 1
            logp(" - Already in DB")
            continue

        try:
            url = _url_after_redirects(feed_item["url"])

            # check if the article after resolving redirects is already in the DB
            art = model.Article.find(url)
            if art:
                skipped_already_in_db += 1
                logp(" - Already in DB")
                continue

        except requests.exceptions.TooManyRedirects:
            raise Exception(f"- Too many redirects")
        except Exception:
            raise Exception(
                f"- Could not get url after redirects for {feed_item['url']}"
            )

        if banned_url(url):
            logp("Banned Url")
            continue

        try:
            new_article = download_feed_item(
                session,
                feed,
                feed_item,
                url,
                crawl_report,
            )
            # Politiken sometimes has titles that have
            # strange characters instead of å æ ø
            if feed.id == 136:
                new_article.title = (
                    new_article.title.replace("Ã¥", "å")
                    .replace("Ã¸", "ø")
                    .replace("Ã¦", "æ")
                )

            downloaded += 1
            if save_in_elastic and not new_article.broken:
                if new_article:
                    index_in_elasticsearch(new_article, session)

            downloaded_titles.append(
                new_article.title + " " + new_article.url.as_string()
            )

        except SkippedForTooOld:
            logp("- Article too old")
            continue

        except SkippedForLowQuality as e:
            logp(f" - Low quality: {e.reason}")
            skipped_due_to_low_quality += 1
            continue

        except SkippedAlreadyInDB:
            skipped_already_in_db += 1
            logp(" - Already in DB")
            continue

        except FailedToParseWithReadabilityServer as e:
            logp(f" - failed to parse with readability server (server said: {e})")
            continue

        except newspaper.ArticleException as e:
            logp(f"Newspaper can't download article at: {url}")
            continue

        except DataError as e:
            logp(f"Data error ({e}) for: {url}")
            continue

        except requests.exceptions.Timeout:
            logp(
                f"The request from the server was timed out after {TIMEOUT_SECONDS} seconds."
            )
            continue

        except Exception as e:
            import traceback

            print(e)
            traceback.print_stack()
            capture_to_sentry(e)
            if hasattr(e, "message"):
                logp(e.message)
            else:
                logp(e)
            continue
    crawl_report.set_feed_total_articles(feed, len(items))
    crawl_report.set_feed_total_downloaded(feed, downloaded)
    crawl_report.set_feed_total_low_quality(feed, skipped_due_to_low_quality)
    crawl_report.set_feed_total_in_db(feed, skipped_already_in_db)
    crawl_report.set_feed_crawl_time(feed, round(time() - start_feed_time, 2))
    summary_stream += (
        f"{downloaded} new articles from {feed.title} ({len(items)} items)\n"
    )
    for each in downloaded_titles:
        summary_stream += f" - {each}\n"

    logp(f"*** Downloaded: {downloaded} From: {feed.title}")
    logp(f"*** Low Quality: {skipped_due_to_low_quality}")
    logp(f"*** Already in DB: {skipped_already_in_db}")
    logp(f"*** ")
    session.commit()

    return summary_stream


def download_feed_item(session, feed, feed_item, url, crawl_report):
    title = feed_item["title"]

    published_datetime = feed_item["published_datetime"]

    art = model.Article.find(url)

    if art:
        raise SkippedAlreadyInDB()

    np_article = readability_download_and_parse(url)

    is_quality_article, reason, code = sufficient_quality(
        np_article, feed.language.code
    )
    if is_quality_article:
        np_article.text = cleanup_text_w_crawl_report(
            np_article.text, crawl_report, feed, url
        )
    summary = feed_item["summary"]
    # however, this is not so easy... there have been cases where
    # the summary is just malformed HTML... thus we try to extract
    # the text:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(summary, "lxml")
    summary = soup.get_text()
    # then there are cases where the summary is huge... so we clip it
    summary = summary[:MAX_CHAR_COUNT_IN_SUMMARY]
    # and if there is still no summary, we simply use the beginning of
    # the article
    if len(summary) < 10:
        summary = np_article.text[:MAX_CHAR_COUNT_IN_SUMMARY]

    # Create new article and save it to DB
    new_article = zeeguu.core.model.Article(
        Url.find_or_create(session, url),
        title,
        ", ".join(np_article.authors),
        np_article.text,
        summary,
        published_datetime,
        feed,
        feed.language,
        htmlContent=np_article.htmlContent,
    )
    session.add(new_article)

    if not is_quality_article:
        MAX_WORD_FOR_BROKEN_ARTICLE = 10000
        crawl_report.add_non_quality_reason(feed, code, str(url))
        new_article.set_as_broken(session, code)
        if len(new_article.content.split()) > MAX_WORD_FOR_BROKEN_ARTICLE:
            new_article.content = new_article.content[:MAX_WORD_FOR_BROKEN_ARTICLE]
        session.add(new_article)
        raise SkippedForLowQuality(reason)

    if np_article.top_image != "":
        # from https://stackoverflow.com/questions/7391945/how-do-i-read-image-data-from-a-url-in-python
        from PIL import Image
        import requests
        from io import BytesIO

        try:
            response = requests.get(np_article.top_image)
            im = Image.open(BytesIO(response.content))
            im_x, im_y = im.size
            # Quality Check that the image is at least 300x300 ( not an icon )
            if im_x < 300 and im_y < 300:
                print("Skipped image due to low resolution")
            else:
                new_article.img_url = Url.find_or_create(session, np_article.top_image)
        except Exception as e:
            print(f"Failed to parse image: '{e}'")

    url_keywords = add_url_keywords(new_article, session)
    logp(f"Topic Keywords: ({url_keywords})")
    if SEMANTIC_SEARCH_AVAILABLE:
        _, topics = add_new_topics(new_article, feed, url_keywords, session)
        logp(f"New Topics ({topics})")
    session.add(new_article)
    return new_article


def add_new_topics(new_article, feed, url_keywords, session):
    HARDCODED_FEEDS = {
        102: 8,  # The Onion EN
        121: 8,  # Lercio IT
    }
    # Handle Hard coded Feeds
    if feed.id in HARDCODED_FEEDS:
        print("Used HARDCODED feed")
        topic = NewTopic.find_by_id(HARDCODED_FEEDS[feed.id])
        new_article.add_new_topic(topic, session, TopicOriginType.HARDSET.value)
        session.add(new_article)
        return TopicOriginType.HARDSET.value, [topic.title]

    # Try setting the Topics based on URLs
    topics = []
    topics_added = set()
    for topic_key in url_keywords:
        topic = topic_key.new_topic
        print(topic_key, topic)
        if (
            topic is not None
        ):  # there could be a keyword that might not have a topic assigned
            if topic.id in topics_added:
                continue
            topics_added.add(topic.id)
            topics.append(topic)
            new_article.add_new_topic(topic, session, TopicOriginType.URL_PARSED.value)

    if len(topics) > 0:
        print("Used URL PARSED")
        session.add(new_article)
        # If we have only one topic and that is News, we will try to infer.
        if not (len(topics) == 1 and 9 in topics_added):
            return TopicOriginType.URL_PARSED.value, [
                t.new_topic.title for t in new_article.new_topics
            ]

    from collections import Counter

    # Add based on KK neighbours:
    found_articles, _ = add_topics_based_on_semantic_hood_search(new_article)
    neighbouring_topics = [t.new_topic for a in found_articles for t in a.new_topics]
    if len(neighbouring_topics) > 0:
        from pprint import pprint

        topics_counter = Counter(neighbouring_topics)
        pprint(topics_counter)
        top_topic, count = topics_counter.most_common(1)[0]
        threshold = (
            sum(topics_counter.values()) // 2
        )  # The threshold is being at least half or above rounded down
        if count >= threshold:
            print(f"Used INFERRED: {top_topic}, {count}, with t={threshold}")
            new_article.add_new_topic(
                top_topic, session, TopicOriginType.INFERRED.value
            )
            session.add(new_article)
            return TopicOriginType.INFERRED.value, [
                t.new_topic.title for t in new_article.new_topics
            ]

    return (
        (None, [])
        if len(topics) == 0
        else (
            TopicOriginType.URL_PARSED.value,
            [t.new_topic.title for t in new_article.new_topics],
        )
    )


def add_url_keywords(new_article, session):
    url_keywords = [
        UrlKeyword.find_or_create(session, keyword, new_article.language)
        for keyword in UrlKeyword.get_url_keywords_from_url(new_article.url)
        if keyword is not None
    ]
    new_article.set_url_keywords(url_keywords, session)
    session.add(new_article)
    return url_keywords
